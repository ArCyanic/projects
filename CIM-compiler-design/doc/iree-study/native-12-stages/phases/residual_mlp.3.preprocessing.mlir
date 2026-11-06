#executable_target_metal_msl_fb = #hal.executable.target<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>
#map = affine_map<(d0, d1) -> (d1)>
#map1 = affine_map<(d0, d1) -> (d0, d1)>
#map2 = affine_map<(d0, d1) -> (d0)>
#device_target_metal = #hal.device.target<"metal", [#executable_target_metal_msl_fb]> : !hal.device
module @residual_mlp attributes {stream.affinity.default = #hal.device.affinity<@__device_0>} {
  util.global private @__device_0 = #device_target_metal
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %cst = arith.constant 0.000000e+00 : f32
    %0 = hal.tensor.import %arg0 "input0" : !hal.buffer_view -> tensor<16x32xf32>
    %1 = hal.tensor.import %arg1 "input1" : !hal.buffer_view -> tensor<32x64xf32>
    %2 = hal.tensor.import %arg2 "input2" : !hal.buffer_view -> tensor<64xf32>
    %3 = hal.tensor.import %arg3 "input3" : !hal.buffer_view -> tensor<64x32xf32>
    %4 = hal.tensor.import %arg4 "input4" : !hal.buffer_view -> tensor<32xf32>
    %5 = hal.tensor.import %arg5 "input5" : !hal.buffer_view -> tensor<16x32xf32>
    %6 = tensor.empty() : tensor<16x64xf32>
    %7 = linalg.fill ins(%cst : f32) outs(%6 : tensor<16x64xf32>) -> tensor<16x64xf32>
    %8 = linalg.matmul ins(%0, %1 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%7 : tensor<16x64xf32>) -> tensor<16x64xf32>
    %9 = linalg.generic {indexing_maps = [#map, #map1], iterator_types = ["parallel", "parallel"]} ins(%2 : tensor<64xf32>) outs(%6 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %out: f32):
      linalg.yield %in : f32
    } -> tensor<16x64xf32>
    %10 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%8, %9 : tensor<16x64xf32>, tensor<16x64xf32>) outs(%6 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %23 = arith.addf %in, %in_0 : f32
      linalg.yield %23 : f32
    } -> tensor<16x64xf32>
    %11 = linalg.generic {indexing_maps = [#map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%10 : tensor<16x64xf32>) outs(%6 : tensor<16x64xf32>) {
    ^bb0(%in: f32, %out: f32):
      %23 = arith.maximumf %in, %cst : f32
      linalg.yield %23 : f32
    } -> tensor<16x64xf32>
    %12 = tensor.empty() : tensor<16x32xf32>
    %13 = linalg.fill ins(%cst : f32) outs(%12 : tensor<16x32xf32>) -> tensor<16x32xf32>
    %14 = linalg.matmul ins(%11, %3 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%13 : tensor<16x32xf32>) -> tensor<16x32xf32>
    %15 = linalg.generic {indexing_maps = [#map, #map1], iterator_types = ["parallel", "parallel"]} ins(%4 : tensor<32xf32>) outs(%12 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %out: f32):
      linalg.yield %in : f32
    } -> tensor<16x32xf32>
    %16 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%14, %15 : tensor<16x32xf32>, tensor<16x32xf32>) outs(%12 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %23 = arith.addf %in, %in_0 : f32
      linalg.yield %23 : f32
    } -> tensor<16x32xf32>
    %17 = linalg.generic {indexing_maps = [#map1, #map1, #map1], iterator_types = ["parallel", "parallel"]} ins(%16, %5 : tensor<16x32xf32>, tensor<16x32xf32>) outs(%12 : tensor<16x32xf32>) {
    ^bb0(%in: f32, %in_0: f32, %out: f32):
      %23 = arith.addf %in, %in_0 : f32
      linalg.yield %23 : f32
    } -> tensor<16x32xf32>
    %18 = tensor.empty() : tensor<16xf32>
    %19 = linalg.fill ins(%cst : f32) outs(%18 : tensor<16xf32>) -> tensor<16xf32>
    %20 = linalg.generic {indexing_maps = [#map1, #map2], iterator_types = ["parallel", "reduction"]} ins(%17 : tensor<16x32xf32>) outs(%19 : tensor<16xf32>) {
    ^bb0(%in: f32, %out: f32):
      %23 = arith.addf %out, %in : f32
      linalg.yield %23 : f32
    } -> tensor<16xf32>
    %21 = hal.tensor.export %17 "output0" : tensor<16x32xf32> -> !hal.buffer_view
    %22 = hal.tensor.export %20 "output1" : tensor<16xf32> -> !hal.buffer_view
    util.return %21, %22 : !hal.buffer_view, !hal.buffer_view
  }
}
