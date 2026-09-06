// Source-backed RyzenAI-SW 1.0 qlinear_2 single token INT8 GEMM fixture.
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
#include <filesystem>
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
static std::vector<char> read(const std::filesystem::path& path) {
  std::ifstream f(path,std::ios::binary|std::ios::ate); if(!f)throw std::runtime_error("cannot open fixture");
  auto size=f.tellg(); if(size<=0||size>16*1024*1024)throw std::runtime_error("invalid fixture size");
  std::vector<char> result(static_cast<size_t>(size)); f.seekg(0); f.read(result.data(),size); if(!f)throw std::runtime_error("short fixture"); return result;
}
int main(int argc,char** argv) {
  std::cout<<std::unitbuf<<std::setprecision(12); const auto process=Clock::now();
  try {
    if(argc!=5)throw std::runtime_error("usage: compute_probe xclbin fixture_dir repetitions(1..10) output_dir");
    const auto fixtures=std::filesystem::path(argv[2]); const auto output_dir=std::filesystem::path(argv[4]);
    if(!std::filesystem::create_directory(output_dir))throw std::runtime_error("output directory must be new");
    int repetitions=std::stoi(argv[3]); if(repetitions<1||repetitions>10)throw std::runtime_error("repetition bound");
    auto a=read(fixtures/"a_with_super_sequence.bin"),w=read(fixtures/"weights_packed_int8.bin"),expected=read(fixtures/"expected_rowmajor_int32.bin"),instr=read(fixtures/"instructions_uint32.bin");
    if(a.size()!=2248||w.size()!=4194304||expected.size()!=8192||instr.size()!=6652)throw std::runtime_error("frozen 1x2048x2048 fixture size mismatch");
    std::cout<<"{\"stage\":\"fixture_read\",\"a_sha256\":\""<<sha256(a.data(),a.size())<<"\",\"weights_sha256\":\""<<sha256(w.data(),w.size())<<"\",\"oracle_sha256\":\""<<sha256(expected.data(),expected.size())<<"\",\"instruction_sha256\":\""<<sha256(instr.data(),instr.size())<<"\"}\n";
    auto dev=xrt::device(0);auto xb=xrt::xclbin(argv[1]);dev.register_xclbin(xb);
    auto ctx=xrt::hw_context(dev,xb.get_uuid());auto kernel=xrt::kernel(ctx,"DPU");
    auto abo=xrt::bo(dev,a.size(),xrt::bo::flags::host_only,kernel.group_id(1));
    auto wbo=xrt::bo(dev,w.size(),xrt::bo::flags::host_only,kernel.group_id(2));
    auto cbo=xrt::bo(dev,expected.size(),xrt::bo::flags::host_only,kernel.group_id(3));
    auto d1=xrt::bo(dev,16,xrt::bo::flags::host_only,kernel.group_id(4));
    auto ibo=xrt::bo(dev,instr.size(),xrt::bo::flags::cacheable,kernel.group_id(5));
    auto d2=xrt::bo(dev,16,xrt::bo::flags::host_only,kernel.group_id(7));
    auto ap=abo.map<char*>();auto wp=wbo.map<char*>();auto cp=cbo.map<char*>();auto ip=ibo.map<char*>();
    std::memcpy(ap,a.data(),a.size());std::memcpy(wp,w.data(),w.size());std::memcpy(ip,instr.data(),instr.size());
    std::memset(d1.map<char*>(),0,16);std::memset(d2.map<char*>(),0,16);
    auto t=Clock::now();ibo.sync(XCL_BO_SYNC_BO_TO_DEVICE);abo.sync(XCL_BO_SYNC_BO_TO_DEVICE);wbo.sync(XCL_BO_SYNC_BO_TO_DEVICE);d1.sync(XCL_BO_SYNC_BO_TO_DEVICE);d2.sync(XCL_BO_SYNC_BO_TO_DEVICE);
    std::cout<<"{\"stage\":\"prelaunch_contract\",\"a_bytes\":"<<a.size()<<",\"weights_bytes\":"<<w.size()<<",\"output_bytes\":"<<expected.size()<<",\"instruction_bytes\":"<<instr.size()<<",\"a_address\":"<<abo.address()<<",\"weights_address\":"<<wbo.address()<<",\"output_address\":"<<cbo.address()<<",\"instruction_address\":"<<ibo.address()<<",\"dummy1_address\":"<<d1.address()<<",\"dummy2_address\":"<<d2.address()<<",\"setup_sync_s\":"<<seconds(t)<<",\"logical_macs\":4194304}\n";
    for(int i=0;i<repetitions;++i) {
      std::memset(cp,0xa5,expected.size());cbo.sync(XCL_BO_SYNC_BO_TO_DEVICE);
      std::cout<<"{\"stage\":\"before_launch\",\"iteration\":"<<i<<",\"output_poison_sha256\":\""<<sha256(cp,expected.size())<<"\"}\n";
      const auto launch_start=Clock::now();t=launch_start;auto run=kernel(uint64_t{1},abo,wbo,cbo,d1,ibo,uint32_t(instr.size()/4),d2);run.wait2(std::chrono::milliseconds(30000));const auto elapsed=seconds(t);
      if(run.state()!=ERT_CMD_STATE_COMPLETED)throw std::runtime_error("not completed");
      t=Clock::now();cbo.sync(XCL_BO_SYNC_BO_FROM_DEVICE);const auto sync_s=seconds(t);
      const auto visible_s=seconds(launch_start);
      size_t mismatches=0;auto got=reinterpret_cast<const int32_t*>(cp);auto want=reinterpret_cast<const int32_t*>(expected.data());
      for(size_t n=0;n<2048;++n)if(got[n]!=want[n])++mismatches;
      const bool unchanged=std::memcmp(ap,a.data(),a.size())==0&&std::memcmp(wp,w.data(),w.size())==0&&std::memcmp(ip,instr.data(),instr.size())==0;
      std::ofstream out(output_dir/("output_"+std::to_string(i)+".bin"),std::ios::binary);out.write(cp,expected.size());out.close();if(!out)throw std::runtime_error("output save failed");
      std::cout<<"{\"stage\":\"result\",\"iteration\":"<<i<<",\"state\":"<<run.state()<<",\"host_launch_wait2_s\":"<<elapsed<<",\"sync_from_device_s\":"<<sync_s<<",\"launch_to_output_sync_s\":"<<visible_s<<",\"compared_int32\":2048,\"mismatches\":"<<mismatches<<",\"inputs_unchanged_host_mapping\":"<<(unchanged?"true":"false")<<",\"output_sha256\":\""<<sha256(cp,expected.size())<<"\",\"numeric_pass\":"<<(!mismatches&&unchanged?"true":"false")<<"}\n";
      if(mismatches||!unchanged)throw std::runtime_error("numerical mismatch");
    }
    std::cout<<"{\"stage\":\"completed\",\"repetitions\":"<<repetitions<<",\"host_main_before_teardown_s\":"<<seconds(process)<<"}\n";return 0;
  } catch(const std::exception& e) {std::cerr<<"FAILED: "<<e.what()<<std::endl;return 1;}
}
