# R5 all frozen cases

Gains are paired-seed mean percentage latency reductions; positive means faster. Intervals are paired-seed bootstrap95%. All hardware timing is hypothetical. GDN main lowering has an RF-residency baseline limitation.

| Backend | Workload | Configuration | S cycles | B0 gain% [CI] | B2 gain% [CI] | Static plans |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| atomic | flux_projection | ref_combined | 79650.175 | +0.0000 [+0.0000,+0.0000] | -0.0184 [-0.0194,-0.0172] | 61 |
| atomic | flux_projection | ref_none | 61679.000 | +0.0000 [+0.0000,+0.0000] | -0.0195 [-0.0195,-0.0195] | 83 |
| atomic | qwen_gdn_state | ref_combined | 25641.841 | +0.0000 [+0.0000,+0.0000] | -0.1007 [-0.1033,-0.0984] | 37 |
| atomic | qwen_gdn_state | ref_none | 24156.000 | +0.0000 [+0.0000,+0.0000] | -0.1076 [-0.1076,-0.1076] | 37 |
| atomic | qwen_projection | ref_combined | 56034.019 | +0.0000 [+0.0000,+0.0000] | -0.0243 [-0.0249,-0.0234] | 79 |
| atomic | qwen_projection | ref_none | 42300.000 | +0.0000 [+0.0000,+0.0000] | -0.0331 [-0.0331,-0.0331] | 79 |
| request | flux_projection | banks1_combined | 76254.102 | -0.6069 [-0.6827,-0.5296] | -0.6583 [-0.7199,-0.6152] | 67 |
| request | flux_projection | fifo_combined | 91335.228 | -1.6814 [-2.2018,-1.1870] | -0.9958 [-1.3810,-0.6085] | 61 |
| request | flux_projection | o1_combined | 791729.941 | -0.3152 [-0.5726,-0.0922] | -0.3330 [-0.5869,-0.1111] | 61 |
| request | flux_projection | o32_combined | 76433.882 | -0.9025 [-1.0257,-0.7824] | -0.9954 [-1.1075,-0.8822] | 61 |
| request | flux_projection | o4_combined | 209591.405 | -0.1817 [-0.2882,-0.0789] | -0.2110 [-0.3785,-0.0674] | 67 |
| request | flux_projection | r1_combined | 280047.834 | -0.2271 [-0.3128,-0.1478] | -0.3084 [-0.3817,-0.2367] | 61 |
| request | flux_projection | r2_combined | 145223.001 | -0.7816 [-1.0174,-0.5398] | -0.8306 [-1.0158,-0.6260] | 67 |
| request | flux_projection | ref_bank_background | 58015.960 | -0.9821 [-1.0500,-0.9239] | -0.9814 [-1.0479,-0.9241] | 61 |
| request | flux_projection | ref_bus_background | 75972.851 | -0.4327 [-0.4923,-0.3668] | -0.4567 [-0.5160,-0.3918] | 61 |
| request | flux_projection | ref_combined | 76700.691 | -1.2792 [-1.5391,-0.9985] | -1.2751 [-1.5081,-1.0216] | 67 |
| request | flux_projection | ref_latency | 57635.617 | -0.5340 [-0.5694,-0.4826] | -0.5653 [-0.6006,-0.5149] | 61 |
| request | flux_projection | ref_none | 57575.000 | -0.5280 [-0.5280,-0.5280] | -0.5662 [-0.5662,-0.5662] | 61 |
| request | qwen_gdn_state | banks1_combined | 26616.354 | +0.0000 [+0.0000,+0.0000] | -0.1517 [-0.2361,-0.0982] | 37 |
| request | qwen_gdn_state | fifo_combined | 32184.334 | +0.0000 [+0.0000,+0.0000] | -2.0157 [-3.4084,-0.6429] | 37 |
| request | qwen_gdn_state | o1_combined | 80239.170 | +0.0000 [+0.0000,+0.0000] | -0.0916 [-0.2458,+0.0453] | 37 |
| request | qwen_gdn_state | o32_combined | 27659.729 | +0.0000 [+0.0000,+0.0000] | -0.2327 [-0.5640,+0.0257] | 37 |
| request | qwen_gdn_state | o4_combined | 37310.643 | +0.0000 [+0.0000,+0.0000] | -0.1531 [-0.3824,+0.0500] | 37 |
| request | qwen_gdn_state | r1_combined | 41200.001 | +0.0000 [+0.0000,+0.0000] | -0.0351 [-0.0619,-0.0079] | 37 |
| request | qwen_gdn_state | r2_combined | 31750.167 | +0.0000 [+0.0000,+0.0000] | -0.0770 [-0.3250,+0.1850] | 37 |
| request | qwen_gdn_state | ref_bank_background | 27117.643 | +0.0000 [+0.0000,+0.0000] | -0.1240 [-0.5197,+0.2572] | 37 |
| request | qwen_gdn_state | ref_bus_background | 24440.667 | +0.0000 [+0.0000,+0.0000] | -0.1853 [-0.3078,-0.0725] | 37 |
| request | qwen_gdn_state | ref_combined | 28149.942 | +0.0000 [+0.0000,+0.0000] | -0.1998 [-0.5185,+0.1563] | 37 |
| request | qwen_gdn_state | ref_latency | 23558.497 | +0.0000 [+0.0000,+0.0000] | -0.0905 [-0.1750,+0.0067] | 37 |
| request | qwen_gdn_state | ref_none | 23318.000 | +0.0000 [+0.0000,+0.0000] | -0.1372 [-0.1372,-0.1372] | 37 |
| request | qwen_projection | banks1_combined | 55324.826 | -0.0836 [-0.1575,-0.0248] | -0.1239 [-0.1936,-0.0664] | 118 |
| request | qwen_projection | fifo_combined | 64819.856 | -0.5326 [-0.9863,-0.0895] | -0.6078 [-1.0215,-0.1967] | 67 |
| request | qwen_projection | o1_combined | 588789.443 | +0.1649 [-0.0253,+0.3458] | +0.1821 [-0.0082,+0.3534] | 61 |
| request | qwen_projection | o32_combined | 55417.262 | +0.0000 [+0.0000,+0.0000] | -0.0832 [-0.1517,-0.0262] | 118 |
| request | qwen_projection | o4_combined | 154322.484 | +0.0908 [-0.0614,+0.2480] | +0.0852 [-0.0910,+0.2922] | 61 |
| request | qwen_projection | r1_combined | 206256.001 | -0.0304 [-0.1244,+0.0543] | -0.0710 [-0.1457,-0.0039] | 61 |
| request | qwen_projection | r2_combined | 106091.667 | -0.0206 [-0.1182,+0.0826] | -0.1106 [-0.2535,+0.0162] | 61 |
| request | qwen_projection | ref_bank_background | 41862.439 | -0.0732 [-0.1548,-0.0044] | -0.1251 [-0.2088,-0.0559] | 118 |
| request | qwen_projection | ref_bus_background | 55328.834 | +0.0000 [+0.0000,+0.0000] | -0.0247 [-0.0253,-0.0238] | 94 |
| request | qwen_projection | ref_combined | 55546.574 | +0.0000 [+0.0000,+0.0000] | -0.0558 [-0.1641,+0.0121] | 118 |
| request | qwen_projection | ref_latency | 41623.048 | -0.2872 [-0.3758,-0.1921] | -0.3122 [-0.3922,-0.2233] | 118 |
| request | qwen_projection | ref_none | 41718.000 | +0.0000 [+0.0000,+0.0000] | -0.0431 [-0.0431,-0.0431] | 94 |
