"""Bounded analytic, metamorphic and negative-audit tests for R5."""
from dataclasses import replace
import copy
import unittest

from r5.model import Command, Graph, Hardware, Plan, Span, build
from r5.resource_sim import Environment, simulate
from r5.replay_audit import audit


def fixture(commands, hw=Hardware(), name='analytic'):
    graph=Graph(name,tuple(commands),{'rf_bytes_per_core':0})
    plan=Plan(tuple(c.cid for c in commands))
    return graph,plan


def run(commands, hw=Hardware(), environment=Environment(), policy='S'):
    graph,plan=fixture(commands,hw)
    result=simulate(graph,hw,plan,environment,policy,detailed=True)
    audit(graph,result)
    return result


class ResourceModelTests(unittest.TestCase):
    def test_single_dma_closed_form(self):
        result=run([Command('x','dma',0,'dma',(),(Span(0,256,'x'),))])
        # dispatch1 + external_latency64 + external8 + fabric(2+4)
        # + bank16 + notification1 = 96.
        self.assertEqual(result['latency'],96)
        self.assertEqual(result['requests'][0]['credit_release'],95)

    def test_same_bank_serializes_distinct_banks_overlap_fixed_total_bw(self):
        hw=replace(Hardware(),banks=2,local_outstanding=2)
        split=run([Command('x','feed',0,'read',(),(Span(0,256,'a'),Span(256,256,'b')))],hw)
        same=run([Command('x','feed',0,'read',(),(Span(0,256,'a'),Span(512,256,'b')))],hw)
        self.assertEqual(split['latency'],8)
        self.assertEqual(same['latency'],10)
        rr=sorted(split['requests'],key=lambda r:r['bank_start'])
        self.assertLess(rr[1]['bank_start'],rr[0]['bank_end'])
        self.assertEqual(rr[1]['bank_start']-rr[0]['bank_start'],256/hw.sram_bw)
        # Banks split a fixed total byte budget; they do not duplicate it.
        for bank_count in (1,2,4,8):
            result=run([Command('x','feed',0,'read',(),(Span(0,2048,'stripe'),))],replace(hw,banks=bank_count,local_outstanding=8))
            self.assertEqual(result['hardware']['sram_bw'],128)
            self.assertEqual(sum(result['metrics']['bank_service_cycles']),2048/(128/bank_count))

    def test_outstanding_credit_closed_form(self):
        hw=replace(Hardware(),banks=1,sram_bw=256,external_latency=10,external_bw=256,fabric_latency=0,fabric_bw=256,return_slots=2)
        command=Command('x','dma',0,'dma',(),(Span(0,512,'two requests'),))
        one=run([command],replace(hw,outstanding=1))
        two=run([command],replace(hw,outstanding=2))
        self.assertEqual(one['latency'],28)
        self.assertEqual(two['latency'],16)
        rows=sorted(one['requests'],key=lambda r:r['index'])
        self.assertEqual(rows[1]['issued'],rows[0]['visible'])

    def test_finite_return_backpressure_closed_form(self):
        hw=replace(Hardware(),banks=1,sram_bw=256,external_latency=10,external_bw=256,fabric_latency=0,fabric_bw=256,outstanding=2)
        command=Command('x','dma',0,'dma',(),(Span(0,512,'two requests'),))
        one=run([command],replace(hw,return_slots=1))
        two=run([command],replace(hw,return_slots=2))
        self.assertEqual(one['latency'],18)
        self.assertEqual(two['latency'],16)
        self.assertGreater(one['metrics']['return_backpressure_union'],0)
        rows=sorted(one['requests'],key=lambda r:r['index'])
        self.assertEqual(rows[1]['external_start'],rows[0]['visible'])

    def test_zero_noise_seeds_and_common_raw_environment(self):
        hw=replace(Hardware(),outstanding=2,return_slots=1)
        commands=[Command('a','dma',0,'dma',(),(Span(0,512,'a'),)),Command('b','dma',1,'dma',(),(Span(2048,512,'b'),))]
        a=run(commands,hw,Environment(seed=3))
        b=run(commands,hw,Environment(seed=101))
        self.assertEqual(a['commands'],b['commands'])
        self.assertEqual(a['requests'],b['requests'])
        e=Environment(seed=73,mode='combined')
        ga,pa=fixture(commands,hw)
        gb,pb=fixture(list(reversed(commands)),hw)
        aa=simulate(ga,hw,pa,e,'S',detailed=True)
        bb=simulate(gb,hw,pb,e,'S',detailed=True)
        audit(ga,aa);audit(gb,bb)
        raw=lambda r:{x['rid']:x['external_latency'] for x in r['requests']}
        self.assertEqual(raw(aa),raw(bb))
        self.assertEqual(aa['environment'],bb['environment'])
        self.assertNotEqual({r['rid']:r['issued'] for r in aa['requests']},{r['rid']:r['issued'] for r in bb['requests']})

    def test_background_bank_always_exists(self):
        for banks in (1,2,4,8):
            for seed in (0,1,7):
                hw=replace(Hardware(),banks=banks,local_outstanding=8)
                run([Command('x','feed',0,'read',(),(Span(0,2048,'stripe'),))],hw,Environment(seed=seed,mode='bank_background',period=64,duty=.5))

    def test_simultaneous_batch_and_renaming(self):
        hw=replace(Hardware(),issue_cycle=0,dispatch=1)
        def commands(a,b):
            return [Command(a,'vpu0',0,'compute',(),cycles=7),Command(b,'vpu1',1,'compute',(),cycles=7),Command('join','mxu0',0,'compute',(a,b),cycles=5)]
        a=run(commands('a','z'),hw)
        b=run(commands('z','a'),hw)
        self.assertEqual(a['latency'],b['latency'])
        self.assertEqual(a['latency'],16)
        self.assertEqual([t['visible'] for t in a['commands'][:2]],[9,9])

    def test_source_slices_and_reuse(self):
        hw=Hardware()
        for name in ('qwen_projection','flux_projection','qwen_gdn_state'):
            graph=build(name,1,hw)
            for policy in ('S','B'):
                result=simulate(graph,hw,Plan(tuple(c.cid for c in graph.commands),bank_color=1),Environment(seed=5,mode='combined'),policy,extra=2 if policy=='B' else 0,detailed=True)
                checked=audit(graph,result)
                self.assertEqual(checked['status'],'PASS')
                if name.endswith('projection'):
                    self.assertEqual(result['metrics']['external_bytes'],graph.metadata['weight_bytes']+graph.metadata['input_bytes'])
                    self.assertEqual(sum(c.macs for c in graph.commands),graph.metadata['weight_macs'])
                else:
                    self.assertEqual(graph.metadata['rf_bytes_per_core'],65536+4*(3*128+2)*4+4*128*4)

    def test_checker_rejects_duplicate_early_visibility_and_wrong_byte(self):
        graph,plan=fixture([Command('x','dma',0,'dma',(),(Span(0,512,'data'),))])
        good=simulate(graph,Hardware(),plan,detailed=True)
        for mode in ('duplicate','visibility','bytes','credit'):
            result=copy.deepcopy(good)
            if mode=='duplicate':result['requests'].append(copy.deepcopy(result['requests'][0]))
            elif mode=='visibility':result['requests'][0]['visible']-=1
            elif mode=='bytes':result['requests'][0]['bytes']+=1
            else:result['requests'][0]['credit_release']-=1
            with self.assertRaises(AssertionError,msg=mode):audit(graph,result)


if __name__=='__main__':
    unittest.main(verbosity=2)
