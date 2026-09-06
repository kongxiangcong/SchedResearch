"""Source-derived, scaled Qwen3.5-4B text decoder blocks; no trained weights.

The current production llm_sched compiler is not imported or validated.
Float64 verifies algebra/layout/state transitions, not BF16 error or model quality.
"""
from __future__ import annotations
import numpy as np
from r4.graph import Case, Node

REV = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
TF_REV = 'f62dc9bf2c90353b442a56e74391fbb8c689b55e'
SOURCE = f'https://github.com/huggingface/transformers/blob/{TF_REV}/src/transformers/models/qwen3_5/modeling_qwen3_5.py'
EPS = 1e-6


def rms(x, w):
    return x / np.sqrt(np.mean(x*x, axis=-1, keepdims=True) + EPS) * (1+w)


def silu(x):
    return x / (1+np.exp(-x))


def _metadata(kind, shape):
    return {'model_repo': 'Qwen/Qwen3.5-4B', 'model_revision': REV,
            'transformers_revision': TF_REV, 'block_kind': kind,
            'source_checkpoint_parameters': 4659865088,
            'numerical_dtype': 'float64', 'checkpoint_dtype': 'BF16 with selected F32 tensors',
            'shape': shape, 'scaled_validation': True,
            'scale_rule': 'hidden/intermediate/full head_dim/linear head_dims divided by 32; original head counts retained',
            'scope': 'single text decoder layer and one cached decode token; excludes vision, embedding/LM head, MTP, full-model quality',
            'macs': 'exact dense products for stated tiny shapes; VPU nonlinear/reduction counts are operation-count estimates, not calibrated cycles',
            'fusion': 'Qwen projections packed into one output-axis fused GEMM; FFN gate/up fused within two intermediate tiles; tiled down outputs reduced before residual',
            'layout': 'numpy row-major; weights represented [in,out] (transpose of checkpoint nn.Linear weights)',
            'state': 'cache read before unique new-cache output; no in-place overwrite of previous state; single writer per tensor',
            'reference': 'independent direct numpy equations; not execution of installed Transformers or trained checkpoint'}


def _ffn(initial, nodes, rng, h, intermediate, residual, prefix='ffn'):
    """Two legal intermediate tiles; each retains gate/up fusion and down reduction."""
    initial['ffn_norm_weight'] = rng.normal(0, .05, h)
    nodes.append(Node('ffn_norm', 'VPU', (residual, 'ffn_norm_weight'), ('ffn_x',), rms,
                      vector_ops=5*h, source=SOURCE+'#L908', fusion='RMSNormZeroCentered'))
    tile = intermediate // 2
    for c in range(2):
        initial[f'ffn_gu_w{c}'] = rng.normal(0, .05, (h, tile*2))
        initial[f'ffn_down_w{c}'] = rng.normal(0, .05, (tile, h))
        nodes.append(Node(f'ffn_gu{c}', 'MXU', ('ffn_x', f'ffn_gu_w{c}'), (f'ffn_gu{c}',),
                          lambda x,w: x@w, macs=h*tile*2, core=c,
                          source=SOURCE+'#L822-L834', fusion='gate/up GEMM output-axis fusion within intermediate tile'))
        nodes.append(Node(f'ffn_swiglu{c}', 'VPU', (f'ffn_gu{c}',), (f'ffn_act{c}',),
                          lambda gu: silu(gu[:len(gu)//2])*gu[len(gu)//2:],
                          vector_ops=5*tile, core=c, source=SOURCE+'#L833-L834', fusion='SiLU times up'))
        nodes.append(Node(f'ffn_down{c}', 'MXU', (f'ffn_act{c}', f'ffn_down_w{c}'), (f'ffn_partial{c}',),
                          lambda x,w: x@w, macs=tile*h, core=c, source=SOURCE+'#L833-L834'))
    nodes.append(Node('ffn_reduce_residual','VPU',(residual,'ffn_partial0','ffn_partial1'),('output',),
                      lambda x,a,b: x+a+b, vector_ops=2*h, source=SOURCE+'#L910',
                      fusion='sum intermediate-tile partials and residual; reassociation checked in FP64'))


def _reference_ffn(initial, x):
    # Deliberately direct untiled algebra: reconstruct the complete FFN matrices.
    z = x * (1+initial['ffn_norm_weight']) / np.sqrt(np.sum(x*x)/len(x)+EPS)
    gu0,gu1 = initial['ffn_gu_w0'],initial['ffn_gu_w1']
    half = gu0.shape[1]//2
    wg = np.concatenate((gu0[:,:half],gu1[:,:half]),axis=1)
    wu = np.concatenate((gu0[:,half:],gu1[:,half:]),axis=1)
    wd = np.concatenate((initial['ffn_down_w0'],initial['ffn_down_w1']),axis=0)
    gate = np.dot(z,wg)
    return x+np.dot((gate/(1+np.exp(-gate)))*np.dot(z,wu),wd)


def _rotary(a, position, rotary_dim):
    freq = 1/(10000000.0**(np.arange(0,rotary_dim,2)/rotary_dim))
    angle = np.concatenate((position*freq,position*freq))
    rot = a[...,:rotary_dim]
    half = rotary_dim//2
    v = rot*np.cos(angle) + np.concatenate((-rot[...,half:],rot[...,:half]),axis=-1)*np.sin(angle)
    return np.concatenate((v,a[...,rotary_dim:]),axis=-1)


def build_full(seed=7):
    rng=np.random.default_rng(seed)
    h,inter,hq,hk,d,prev,rd=80,288,16,4,8,16,2
    qwidth=hq*d*2; kwidth=hk*d
    p=qwidth+2*kwidth
    init={'input':rng.normal(0,.3,h), 'input_norm_weight':rng.normal(0,.05,h),
          'qkv_gate_weight':rng.normal(0,.05,(h,p)),
          'qk_norm_weight':rng.normal(0,.05,(2,d)),
          'kv_previous':rng.normal(0,.1,(2,prev,hk,d)),
          'out_weight':rng.normal(0,.05,(hq*d,h))}
    nodes=[Node('input_norm','VPU',('input','input_norm_weight'),('normalized',),rms,
                vector_ops=5*h,source=SOURCE+'#L883',fusion='RMSNormZeroCentered'),
           Node('qkv_gate','MXU',('normalized','qkv_gate_weight'),('projected',),lambda x,w:x@w,
                macs=h*p,source=SOURCE+'#L758-L788',fusion='Q+gate,K,V output-axis GEMM fusion')]
    def norm_rope(y,w):
        qg=y[:qwidth].reshape(hq,2*d)
        q=rms(qg[:,:d],w[0]); gate=qg[:,d:].copy()
        k=rms(y[qwidth:qwidth+kwidth].reshape(hk,d),w[1])
        return _rotary(q,prev,rd),_rotary(k,prev,rd),y[qwidth+kwidth:].reshape(hk,d).copy(),gate
    nodes.append(Node('qk_norm_rope','VPU',('projected','qk_norm_weight'),('query','key_new','value_new','gate'),
                      norm_rope,vector_ops=(hq+hk)*(5*d+6*rd),source=SOURCE+'#L780-L793',
                      fusion='per-head Q/K zero-centered RMSNorm plus partial RoPE; views for V/gate'))
    nodes.append(Node('kv_append','VPU',('kv_previous','key_new','value_new'),('kv_next',),
                      lambda kv,k,v:np.concatenate((kv,np.stack((k,v))[:,None]),axis=1),
                      vector_ops=2*(prev+1)*hk*d,core=1,source=SOURCE+'#L795-L796',
                      fusion='logical KV append; scheduler buffer output is full cache, copy cost is an implementation assumption'))
    for c in range(2):
        start,end=c*(hq//2),(c+1)*(hq//2)
        def scores(q,kv,start=start,end=end):
            expanded=np.repeat(kv[0],hq//hk,axis=1)
            return np.einsum('hd,lhd->hl',q[start:end],expanded[:,start:end])/np.sqrt(d)
        def probs(s):
            e=np.exp(s-np.max(s,axis=-1,keepdims=True))
            return e/np.sum(e,axis=-1,keepdims=True)
        def weighted(prob,kv,start=start,end=end):
            expanded=np.repeat(kv[1],hq//hk,axis=1)
            return np.einsum('hl,lhd->hd',prob,expanded[:,start:end])
        nodes.extend((Node(f'qk_matmul{c}','MXU',('query','kv_next'),(f'scores{c}',),scores,
                           macs=(hq//2)*(prev+1)*d,core=c,source=SOURCE+'#L724-L727',
                           fusion='independent query-head tile; GQA repetition is a broadcast view'),
                      Node(f'softmax{c}','VPU',(f'scores{c}',),(f'probability{c}',),probs,
                           vector_ops=5*(hq//2)*(prev+1),core=c,source=SOURCE+'#L731-L732'),
                      Node(f'av_matmul{c}','MXU',(f'probability{c}','kv_next'),(f'context{c}',),weighted,
                           macs=(hq//2)*(prev+1)*d,core=c,source=SOURCE+'#L733-L734')))
    nodes.extend((Node('attention_gate','VPU',('context0','context1','gate'),('gated_context',),
                       lambda a,b,g:(np.concatenate((a,b))/(1+np.exp(-g))).reshape(-1),
                       vector_ops=4*hq*d,source=SOURCE+'#L816',fusion='concatenate head tiles and sigmoid output gating'),
                  Node('attention_out','MXU',('gated_context','out_weight'),('mix_output',),lambda x,w:x@w,
                       macs=hq*d*h,source=SOURCE+'#L818'),
                  Node('attention_residual','VPU',('input','mix_output'),('residual',),lambda x,y:x+y,
                       vector_ops=h,source=SOURCE+'#L904')))
    _ffn(init,nodes,rng,h,inter,'residual')
    # Reference is a direct per-head calculation, with no graph-node invocation.
    xx=init['input']; u=xx*(1+init['input_norm_weight'])/np.sqrt(np.sum(xx*xx)/h+EPS)
    y=np.dot(u,init['qkv_gate_weight']); qg=y[:qwidth].reshape(hq,2*d)
    q=qg[:,:d]*(1+init['qk_norm_weight'][0])/np.sqrt(np.sum(qg[:,:d]**2,axis=1,keepdims=True)/d+EPS)
    k=y[qwidth:qwidth+kwidth].reshape(hk,d)
    k=k*(1+init['qk_norm_weight'][1])/np.sqrt(np.sum(k*k,axis=1,keepdims=True)/d+EPS)
    # rd=2 is precisely the original 64 rotary dimensions scaled by 32.
    for vectors in (q,k):
        a,b=vectors[:,0].copy(),vectors[:,1].copy()
        vectors[:,0]=a*np.cos(prev)-b*np.sin(prev)
        vectors[:,1]=b*np.cos(prev)+a*np.sin(prev)
    v=y[qwidth+kwidth:].reshape(hk,d)
    kv=np.empty((2,prev+1,hk,d));kv[:,:prev]=init['kv_previous'];kv[0,-1]=k;kv[1,-1]=v
    ctx=[]
    for head in range(hq):
        group=head//(hq//hk)
        s=np.dot(kv[0,:,group],q[head])/np.sqrt(d)
        z=np.exp(s-max(s));z/=sum(z)
        ctx.append(np.dot(z,kv[1,:,group])/(1+np.exp(-qg[head,d:])))
    residual=xx+np.dot(np.asarray(ctx).reshape(-1),init['out_weight'])
    ref={'output':_reference_ffn(init,residual),'kv_next':kv}
    meta=_metadata('full_attention_cached_decode',{'hidden':h,'intermediate':inter,'q_heads':hq,'kv_heads':hk,
                    'head_dim':d,'kv_previous_length':prev,'tokens':1,'rotary_dim':rd})
    meta['causal_mask']='one decode query at position previous_length can attend every previous key and itself; no future columns exist'
    meta['conditioning']='text-only; no CFG or visual input; text token has same t/h/w position so multimodal RoPE reduces to ordinary partial RoPE'
    return Case('qwen35_full_decode',init,nodes,('output','kv_next'),ref,meta)


def build_linear(seed=8):
    rng=np.random.default_rng(seed)
    h,inter,hk,hv,dk,dv,kernel=80,288,16,32,4,4,4
    kd=hk*dk;vd=hv*dv;qdim=2*kd+vd;p=qdim+vd+2*hv
    init={'input':rng.normal(0,.3,h),'input_norm_weight':rng.normal(0,.05,h),
          'in_projection_weight':rng.normal(0,.05,(h,p)),
          'conv_weight':rng.normal(0,.15,(qdim,kernel)),
          'conv_previous':rng.normal(0,.1,(qdim,kernel)),
          'decay_parameters':np.stack((rng.normal(-1,.1,hv),rng.normal(0,.1,hv))),
          'gate_norm_weight':rng.normal(1,.05,dv),
          'out_weight':rng.normal(0,.05,(vd,h))}
    for c in range(2):init[f'state_previous{c}']=rng.normal(0,.1,(hv//2,dk,dv))
    nodes=[Node('input_norm','VPU',('input','input_norm_weight'),('normalized',),rms,
                vector_ops=5*h,source=SOURCE+'#L883',fusion='RMSNormZeroCentered'),
           Node('input_projection','MXU',('normalized','in_projection_weight'),('projected',),lambda x,w:x@w,
                macs=h*p,source=SOURCE+'#L549-L584',fusion='QKV,Z,B,A output-axis GEMM fusion')]
    def conv(y,w,state):
        nxt=np.concatenate((state[:,1:],y[:qdim,None]),axis=1)
        return silu(np.sum(nxt*w,axis=1)),nxt
    nodes.append(Node('causal_conv','VPU',('projected','conv_weight','conv_previous'),('conv_qkv','conv_next'),conv,
                      vector_ops=qdim*(2*kernel+4),source=SOURCE+'#L248-L269',fusion='depthwise conv4, SiLU and conv-state shift'))
    def gates(y,pars):
        z=y[qdim:qdim+vd].reshape(hv,dv)
        b=y[qdim+vd:qdim+vd+hv];a=y[qdim+vd+hv:]
        return z,1/(1+np.exp(-b)),-np.exp(pars[0])*np.logaddexp(0,a+pars[1])
    nodes.append(Node('decay_gates','VPU',('projected','decay_parameters'),('z_gate','beta','log_decay'),gates,
                      vector_ops=10*hv,core=1,source=SOURCE+'#L615-L617',fusion='view Z; sigmoid B; FP32-source decay expression'))
    def qk_l2(qkv):
        q=qkv[:kd].reshape(hk,dk);k=qkv[kd:2*kd].reshape(hk,dk)
        q=q/np.sqrt(np.sum(q*q,axis=-1,keepdims=True)+EPS)/np.sqrt(dk)
        k=k/np.sqrt(np.sum(k*k,axis=-1,keepdims=True)+EPS)
        return np.repeat(q,hv//hk,axis=0),np.repeat(k,hv//hk,axis=0),qkv[2*kd:].reshape(hv,dv).copy()
    nodes.append(Node('qk_l2_expand','VPU',('conv_qkv',),('query','key','value'),qk_l2,
                      vector_ops=7*hk*dk,source=SOURCE+'#L455-L463',fusion='QK L2 normalization and grouped-head broadcast'))
    for c in range(2):
        start,end=c*(hv//2),(c+1)*(hv//2)
        def recurrence(q,k,v,b,g,state,start=start,end=end):
            qs,ks,vs=q[start:end],k[start:end],v[start:end]
            decayed=state*np.exp(g[start:end,None,None])
            old_v=np.einsum('hkv,hk->hv',decayed,ks)
            delta=(vs-old_v)*b[start:end,None]
            nxt=decayed+ks[:,:,None]*delta[:,None,:]
            return np.einsum('hkv,hk->hv',nxt,qs),nxt
        nodes.append(Node(f'delta_recurrence{c}','VPU',('query','key','value','beta','log_decay',f'state_previous{c}'),
                          (f'context{c}',f'state_next{c}'),recurrence,
                          vector_ops=(hv//2)*(7*dk*dv+3*dv+1),core=c,
                          source=SOURCE+'#L475-L491',fusion='single-token gated DeltaNet state update/read per head tile'))
        def normgate(context,z,w,start=start,end=end):
            norm=context/np.sqrt(np.mean(context*context,axis=-1,keepdims=True)+EPS)
            return (norm*w*silu(z[start:end])).reshape(-1)
        nodes.append(Node(f'gated_norm{c}','VPU',(f'context{c}','z_gate','gate_norm_weight'),(f'normed{c}',),normgate,
                          vector_ops=10*(hv//2)*dv,core=c,source=SOURCE+'#L223-L232',fusion='RMSNorm with direct weight, then SiLU Z'))
    nodes.append(Node('context_concat','VPU',('normed0','normed1'),('all_context',),lambda a,b:np.concatenate((a,b)),
                      vector_ops=vd,source=SOURCE+'#L658',fusion='head tile concatenate'))
    nodes.extend((Node('mix_out','MXU',('all_context','out_weight'),('mix_output',),lambda x,w:x@w,
                       macs=vd*h,source=SOURCE+'#L660'),
                  Node('mix_residual','VPU',('input','mix_output'),('residual',),lambda x,y:x+y,
                       vector_ops=h,source=SOURCE+'#L904')))
    _ffn(init,nodes,rng,h,inter,'residual')
    # Independent direct reference, with scalar head/key/value loops for state update.
    x=init['input'];u=x*(1+init['input_norm_weight'])/np.sqrt(np.sum(x*x)/h+EPS)
    y=np.dot(u,init['in_projection_weight'])
    convnext=np.column_stack((init['conv_previous'][:,1:],y[:qdim]))
    cv=np.array([sum(convnext[j,t]*init['conv_weight'][j,t] for t in range(kernel)) for j in range(qdim)])
    cv=cv/(1+np.exp(-cv))
    queries=cv[:kd].reshape(hk,dk);keys=cv[kd:2*kd].reshape(hk,dk);values=cv[2*kd:].reshape(hv,dv)
    old=np.concatenate((init['state_previous0'],init['state_previous1']),axis=0)
    state=old.copy();contexts=[]
    for head in range(hv):
        group=head//(hv//hk)
        q=queries[group]/np.sqrt(sum(queries[group]**2)+EPS)/np.sqrt(dk)
        k=keys[group]/np.sqrt(sum(keys[group]**2)+EPS)
        beta=1/(1+np.exp(-y[qdim+vd+head]))
        log_decay=-np.exp(init['decay_parameters'][0,head])*np.logaddexp(0,y[qdim+vd+hv+head]+init['decay_parameters'][1,head])
        sd=old[head]*np.exp(log_decay)
        for vindex in range(dv):
            delta=beta*(values[head,vindex]-sum(k[j]*sd[j,vindex] for j in range(dk)))
            for j in range(dk):state[head,j,vindex]=sd[j,vindex]+k[j]*delta
        o=np.array([sum(q[j]*state[head,j,vindex] for j in range(dk)) for vindex in range(dv)])
        z=y[qdim+head*dv:qdim+(head+1)*dv]
        contexts.append(o/np.sqrt(sum(o*o)/dv+EPS)*init['gate_norm_weight']*(z/(1+np.exp(-z))))
    residual=x+np.dot(np.asarray(contexts).reshape(-1),init['out_weight'])
    ref={'output':_reference_ffn(init,residual),'conv_next':convnext,
         'state_next0':state[:hv//2], 'state_next1':state[hv//2:]}
    meta=_metadata('gated_deltanet_cached_decode',{'hidden':h,'intermediate':inter,'key_heads':hk,'value_heads':hv,
                    'key_dim':dk,'value_dim':dv,'conv_kernel':kernel,'tokens':1})
    meta['conditioning']='text-only; no CFG; linear recurrent layers do not use RoPE or a growing KV cache'
    meta['storage_bytes']={k:4 for k in ('state_previous0','state_previous1','state_next0','state_next1',
                                       'decay_parameters','log_decay','gate_norm_weight')}
    meta['storage_note']='default BF16 activations/weights; FP32 recurrent state and decay/gated-norm parameters; packed dt_bias promoted to FP32 to share A_log pack (research layout choice)'
    return Case('qwen35_linear_decode',init,nodes,tuple(ref),ref,meta)


def build_cases(seed=7):
    return [build_full(seed),build_linear(seed+1)]


def build_attention_fused(seed=7):
    """Head-tile attention fusion sensitivity, preserving the independent reference.

    This is a legal mathematical fused task boundary, not an implementation or
    performance claim for a production FlashAttention/NPU kernel. Score and
    probability intermediates stay inside the aggregate task. The simulator
    conservatively reserves MXU, VPU and SRAM throughout all sequential phases.
    """
    case=build_full(seed)
    base_values=case.evaluate()
    byname={node.name:node for node in case.nodes}
    replacements={}
    removed=set()
    internal_scratch={}
    for core in range(2):
        qk=byname[f'qk_matmul{core}']
        softmax=byname[f'softmax{core}']
        av=byname[f'av_matmul{core}']
        def run(query,kv,qk=qk,softmax=softmax,av=av):
            return av.run(softmax.run(qk.run(query,kv)),kv)
        replacements[qk.name]=Node(f'attention_fused{core}','MXU+VPU',
            qk.reads,av.writes,run,macs=qk.macs+softmax.macs+av.macs,
            vector_ops=qk.vector_ops+softmax.vector_ops+av.vector_ops,
            core=core,source=SOURCE+'#L724-L735',
            fusion='head-tile QK/softmax/AV; scores/probabilities engine-internal; conservative whole-task MXU+VPU+SRAM reservation')
        internal_keys=set(qk.writes+softmax.writes)
        internal_scratch[f'attention_fused{core}']={
            'bytes':sum(int(base_values[key].size)*2 for key in internal_keys),
            'traffic_bytes':sum(int(base_values[key].size)*2
                for node in (qk,softmax,av) for key in node.reads+node.writes if key in internal_keys),
            'scope':'BF16 sum of materialized score/probability tensors as conservative retained-buffer scratch; internal tensor reads and writes both counted; no online-softmax claim, no NumPy FP64 temporary-allocation model'}
        removed.update((softmax.name,av.name))
    case.nodes=[replacements.get(n.name,n) for n in case.nodes if n.name not in removed]
    case.name='qwen35_full_decode_attention_fused'
    case.metadata=dict(case.metadata)
    case.metadata['internal_scratch']=internal_scratch
    case.metadata['attention_fusion']='QK/softmax/AV per head tile as one aggregate task; same algebra and reference; score/probability buffers internal to engine'
    case.metadata['engine_reservation']='MXU+VPU+SRAM atomically reserved for full task including sequential matrix/vector phases; conservative occupancy research assumption'
    case.metadata['scope']+='; attention fusion sensitivity does not validate FlashAttention or an implemented NPU fused kernel'
    return case


if __name__=='__main__':
    import json
    for case in build_cases():
        actual=case.evaluate()
        errors={k:float(np.max(np.abs(actual[k]-case.reference[k]))) for k in case.outputs}
        assert max(errors.values())<1e-10,errors
        print(json.dumps({'case':case.name,'nodes':len(case.nodes),'max_abs_error':errors,
                          'macs':sum(n.macs for n in case.nodes)},indent=2))
