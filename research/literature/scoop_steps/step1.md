# Step 1 — Decompose the Novelty

日期：2026-09-05。状态：完成当前限定scope；未取得全文的候选保留限制。

## Decomposed claim

- **Problem framing**：编译期图/地址已知、执行完成时刻未知的 NPU，比较同一合法执行空间中的强静态与动态 dispatch。
- **Core mechanism**：编译器编码依赖、合法位置与资源条件；运行时仅维护有限 completion/ready/resource 状态。
- **Key insight**：将全图 reasoning 离线化，只把剩余运行时信息交给硬件，避免重复实现复杂 scheduler。
- **Application domain**：端侧多核/多 cluster/多 chip AI accelerator，LLM 与 DiT 的 inference execution。

