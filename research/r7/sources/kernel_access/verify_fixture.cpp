// CPU-only independent check against the original frozen AMD helper headers.
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>
#include "ryzenai/example/transformers/ops/cpp/utils/super_instr.h"
#include "ryzenai/example/transformers/ops/cpp/utils/wgt_matrix.h"

static std::vector<char> read(const std::string &name) {
  std::ifstream f(name, std::ios::binary);
  if (!f) throw std::runtime_error("cannot read " + name);
  return std::vector<char>(std::istreambuf_iterator<char>(f), {});
}

int main(int argc, char **argv) {
  try {
    const std::string dir = argc > 1 ? argv[1] : "int8_fixture";
    auto seq = read(dir + "/super_sequence.bin");
    GemmSeq source_seq{}; // Defined zero unused/padding bytes, same as fixture.
    init_gemm_instr_ddr(reinterpret_cast<int8_t *>(&source_seq), 1, 2048, 2048, 32);
    if (seq.size() != sizeof(source_seq) ||
        std::memcmp(seq.data(), &source_seq, seq.size()) != 0)
      throw std::runtime_error("super sequence differs from original C++ helper");
    auto raw = read(dir + "/weights_rowmajor_int8.bin");
    auto packed = read(dir + "/weights_packed_int8.bin");
    auto input = read(dir + "/a_rowmajor_int8.bin");
    auto expected = read(dir + "/expected_rowmajor_int32.bin");
    if (raw.size() != 4194304 || packed.size() != 4194304 ||
        input.size() != 2048 || expected.size() != 8192)
      throw std::runtime_error("fixture length mismatch");
    std::vector<int8_t> source_packed(raw.size(), 0);
    WgtMatrix<int8_t> matrix(source_packed.data(), 2048, 2048);
    for (int r = 0; r < 2048; ++r)
      for (int c = 0; c < 2048; ++c)
        matrix(r, c) = static_cast<int8_t>(raw[r * 2048 + c]);
    if (std::memcmp(source_packed.data(), packed.data(), packed.size()) != 0)
      throw std::runtime_error("packed weights differ from original C++ helper");
    for (int c = 0; c < 2048; ++c) {
      int64_t sum = 0;
      for (int r = 0; r < 2048; ++r)
        sum += int64_t(static_cast<int8_t>(input[r])) *
               int64_t(static_cast<int8_t>(raw[r * 2048 + c]));
      int32_t golden;
      std::memcpy(&golden, expected.data() + 4 * c, 4);
      if (sum != golden) throw std::runtime_error("INT64 oracle mismatch");
    }
    std::cout << "PASS CPU-only source-header check: MLKernelParams="
              << sizeof(MLKernelParams) << " GemmInstr=" << sizeof(GemmInstr)
              << " GemmSeq=" << sizeof(GemmSeq)
              << " packed_weight_bytes=" << packed.size()
              << " exact_oracle_outputs=2048\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL " << e.what() << '\n';
    return 1;
  }
}
