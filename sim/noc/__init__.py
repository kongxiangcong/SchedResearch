"""Finite-capacity links are explicit task resources, not a packet NoC model."""


def transfer_resources(src_chip, src_cluster, dst_chip, dst_cluster):
    if src_chip != dst_chip:
        return (f"chip{src_chip}.egress", f"chip{dst_chip}.ingress", "interchip.link")
    if src_cluster != dst_cluster:
        return (f"chip{src_chip}.noc",)
    return (f"chip{src_chip}.cluster{src_cluster}.sram",)
