// Fixed vendor copy ABI; project-owned initialization, evidence and comparison.
#include "xrt/xrt_device.h"
#include "xrt/xrt_bo.h"
#include "xrt/xrt_kernel.h"
#include "xrt/xrt_hw_context.h"
#include "experimental/xrt_xclbin.h"
#include <windows.h>
#include <bcrypt.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point t) {return std::chrono::duration<double>(Clock::now()-t).count();}
static std::string sha256(const void* data,size_t size) {
  BCRYPT_ALG_HANDLE alg=nullptr; BCRYPT_HASH_HANDLE hash=nullptr;
  if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0) throw std::runtime_error("hash provider");
  if(BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0)<0) throw std::runtime_error("hash create");
  if(BCryptHashData(hash,(PUCHAR)data,(ULONG)size,0)<0) throw std::runtime_error("hash data");
  unsigned char result[32];
  if(BCryptFinishHash(hash,result,32,0)<0) throw std::runtime_error("hash finish");
  BCryptDestroyHash(hash); BCryptCloseAlgorithmProvider(alg,0);
  std::ostringstream out; out<<std::hex<<std::setfill('0');
  for(auto x:result) out<<std::setw(2)<<unsigned(x);
  return out.str();
}
static uint32_t pattern(uint32_t i) {
  // Bijection on 32-bit words; no short periodic pattern across 1GiB.
  i ^= 0x72657337u; i ^= i>>16; i *= 0x7feb352du; i ^= i>>15; i *= 0x846ca68bu; return i^(i>>16);
}
int main(int argc,char** argv) {
  std::cout<<std::unitbuf<<std::setprecision(12);
  const auto process=Clock::now();
  try {
    if(argc!=4) throw std::runtime_error("usage: copy_probe xclbin instruction_file repetitions(1..10)");
    int repetitions=std::stoi(argv[3]); if(repetitions<1||repetitions>10) throw std::runtime_error("repetition bound");
    constexpr size_t bytes=1024ull*1024*1024, words=bytes/4;
    std::vector<uint32_t> instruction;
    std::ifstream in(argv[2]); if(!in) throw std::runtime_error("instruction file");
    std::string line;
    while(std::getline(in,line)) {if(line.empty()||line[0]=='#')continue; instruction.push_back(static_cast<uint32_t>(std::stoul(line,nullptr,16)));}
    if(instruction.empty()) throw std::runtime_error("empty instructions");
    std::cout<<"{\"stage\":\"instruction_read\",\"words\":"<<instruction.size()<<",\"sha256\":\""<<sha256(instruction.data(),instruction.size()*4)<<"\"}\n";
    auto dev=xrt::device(0); auto xb=xrt::xclbin(argv[1]); dev.register_xclbin(xb);
    auto ctx=xrt::hw_context(dev,xb.get_uuid()); auto kernel=xrt::kernel(ctx,"DPU_PDI_0");
    auto input=xrt::bo(dev,bytes,xrt::bo::flags::host_only,kernel.group_id(1));
    auto output=xrt::bo(dev,bytes,xrt::bo::flags::host_only,kernel.group_id(3));
    auto instructions=xrt::bo(dev,instruction.size()*4,xrt::bo::flags::cacheable,kernel.group_id(5));
    auto ip=input.map<uint32_t*>(); auto op=output.map<uint32_t*>(); auto sp=instructions.map<uint32_t*>();
    auto t=Clock::now();
    for(size_t i=0;i<words;++i) ip[i]=pattern(static_cast<uint32_t>(i));
    std::memcpy(sp,instruction.data(),instruction.size()*4);
    auto input_sha=sha256(ip,bytes);
    std::cout<<"{\"stage\":\"prelaunch_contract\",\"logical_input_bytes\":"<<bytes<<",\"logical_output_bytes\":"<<bytes<<",\"input_sha256\":\""<<input_sha<<"\",\"input_bo_address\":"<<input.address()<<",\"output_bo_address\":"<<output.address()<<",\"instruction_bo_address\":"<<instructions.address()<<",\"input_group\":"<<kernel.group_id(1)<<",\"output_group\":"<<kernel.group_id(3)<<",\"instruction_group\":"<<kernel.group_id(5)<<",\"initialization_hash_s\":"<<seconds(t)<<"}\n";
    double timer_min=1e9,timer_sum=0;
    for(int i=0;i<1000;++i){t=Clock::now();auto d=seconds(t);timer_sum+=d;if(d<timer_min)timer_min=d;}
    std::cout<<"{\"stage\":\"host_timer_only\",\"count\":1000,\"mean_s\":"<<timer_sum/1000<<",\"min_s\":"<<timer_min<<",\"device_empty_run\":false}\n";
    for(int iteration=0;iteration<repetitions;++iteration) {
      t=Clock::now(); std::memset(op,0xa5,bytes); const auto poison_sha=sha256(op,bytes);
      const double poison_s=seconds(t);
      t=Clock::now(); instructions.sync(XCL_BO_SYNC_BO_TO_DEVICE); input.sync(XCL_BO_SYNC_BO_TO_DEVICE); output.sync(XCL_BO_SYNC_BO_TO_DEVICE); const double to_device_s=seconds(t);
      std::cout<<"{\"stage\":\"before_launch\",\"iteration\":"<<iteration<<",\"output_poison_sha256\":\""<<poison_sha<<"\",\"poison_hash_s\":"<<poison_s<<",\"all_sync_to_device_s\":"<<to_device_s<<"}\n";
      t=Clock::now();
      auto run=kernel(uint64_t{1},input,NULL,output,NULL,instructions,uint32_t(instruction.size()),NULL);
      run.wait2(std::chrono::milliseconds(30000));
      const double launch_wait_s=seconds(t);
      auto state=run.state(); if(state!=ERT_CMD_STATE_COMPLETED) throw std::runtime_error("run not completed");
      t=Clock::now(); output.sync(XCL_BO_SYNC_BO_FROM_DEVICE); const double from_device_s=seconds(t);
      t=Clock::now(); size_t mismatches=0, first_mismatch=words;
      for(size_t i=0;i<words;++i) if(op[i]!=ip[i]) {++mismatches;if(first_mismatch==words)first_mismatch=i;}
      auto output_sha=sha256(op,bytes); auto after_sha=sha256(ip,bytes);
      const double verify_s=seconds(t);
      std::cout<<"{\"stage\":\"result\",\"iteration\":"<<iteration<<",\"state\":"<<state<<",\"host_launch_wait2_s\":"<<launch_wait_s<<",\"sync_from_device_s\":"<<from_device_s<<",\"launch_to_output_sync_s\":"<<launch_wait_s+from_device_s<<",\"verify_hash_s\":"<<verify_s<<",\"compared_words\":"<<words<<",\"mismatches\":"<<mismatches<<",\"input_unchanged\":"<<(after_sha==input_sha?"true":"false")<<",\"output_sha256\":\""<<output_sha<<"\",\"numeric_pass\":"<<(!mismatches&&output_sha==input_sha&&after_sha==input_sha?"true":"false")<<"}\n";
      if(mismatches||output_sha!=input_sha||after_sha!=input_sha) throw std::runtime_error("numeric verification failed");
    }
    std::cout<<"{\"stage\":\"completed\",\"repetitions\":"<<repetitions<<",\"host_main_before_teardown_s\":"<<seconds(process)<<"}\n";
    return 0;
  } catch(const std::exception& e) {std::cerr<<"FAILED: "<<e.what()<<std::endl;return 1;}
}
