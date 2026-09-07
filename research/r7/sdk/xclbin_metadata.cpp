#include "experimental/xrt_xclbin.h"
#include "xrt/xrt_device.h"
#include "xrt/xrt_kernel.h"
#include "xrt/xrt_bo.h"
#include "xrt/xrt_hw_context.h"
#include <iostream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <windows.h>

// Parsing metadata creates no device, context, BO, or run.
int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: xclbin_metadata.exe XCLBIN\n";
    return 2;
  }
  try {
    char loaded_dll[32768]{};
    const auto module = GetModuleHandleA("xrt_coreutil.dll");
    if (!module || !GetModuleFileNameA(module, loaded_dll, sizeof(loaded_dll)))
      throw std::runtime_error("Cannot identify loaded xrt_coreutil.dll");
    std::cout << "loaded_xrt_coreutil " << std::quoted(loaded_dll) << "\n";
    const xrt::xclbin binary{std::string(argv[1])};
    std::cout << "xclbin " << std::quoted(argv[1]) << "\n";
    std::cout << "uuid " << binary.get_uuid().to_string() << "\n";
    for (const auto& mem : binary.get_mems())
      std::cout << "memory index=" << mem.get_index() << " tag=" << std::quoted(mem.get_tag())
                << " size_kb=" << mem.get_size_kb() << " type=" << static_cast<int>(mem.get_type()) << "\n";
    for (const auto& kernel : binary.get_kernels()) {
      std::cout << "kernel " << std::quoted(kernel.get_name()) << "\n";
      for (const auto& arg : kernel.get_args()) {
        std::cout << "  arg index=" << arg.get_index() << " name=" << std::quoted(arg.get_name())
                  << " type=" << std::quoted(arg.get_host_type()) << " size=" << arg.get_size()
                  << " offset=" << arg.get_offset() << " memory_indices=";
        for (const auto& mem : arg.get_mems()) std::cout << mem.get_index() << ",";
        std::cout << "\n";
      }
    }
    std::cout << "device_opened false\n";
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "ERROR " << ex.what() << "\n";
    return 1;
  }
}
