#executable_target_metal_msl_fb = #hal.executable.target<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>
#map = affine_map<(d0, d1) -> (d0, d1)>
#map1 = affine_map<(d0, d1) -> (d1)>
#map2 = affine_map<(d0, d1) -> (d0)>
#device_target_metal = #hal.device.target<"metal", [#executable_target_metal_msl_fb]> : !hal.device
module @residual_mlp attributes {stream.affinity.default = #hal.device.affinity<@__device_0>} {
  util.global private @__device_0 = #device_target_metal
  flow.executable private @main_dispatch_0 {
    flow.executable.export public @main_dispatch_0_matmul_16x64x32_f32 workgroups() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    builtin.module {
      func.func @main_dispatch_0_matmul_16x64x32_f32(%arg0: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg1: !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>>, %arg2: !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>>, %arg3: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>) {
        %cst = arith.constant 0.000000e+00 : f32
        %0 = iree_tensor_ext.dispatch.tensor.load %arg0, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
        %1 = iree_tensor_ext.dispatch.tensor.load %arg1, offsets = [0, 0], sizes = [32, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>> -> tensor<32x64xf32>
        %2 = iree_tensor_ext.dispatch.tensor.load %arg2, offsets = [0], sizes = [64], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>> -> tensor<64xf32>
        %3 = tensor.empty() : tensor<16x64xf32>
        %4 = linalg.fill ins(%cst : f32) outs(%3 : tensor<16x64xf32>) -> tensor<16x64xf32>
        %5 = linalg.matmul ins(%0, %1 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%4 : tensor<16x64xf32>) -> tensor<16x64xf32>
        %6 = linalg.generic {indexing_maps = [#map, #map1, #map], iterator_types = ["parallel", "parallel"]} ins(%5, %2 : tensor<16x64xf32>, tensor<64xf32>) outs(%3 : tensor<16x64xf32>) {
        ^bb0(%in: f32, %in_0: f32, %out: f32):
          %7 = arith.addf %in, %in_0 : f32
          %8 = arith.maximumf %7, %cst : f32
          linalg.yield %8 : f32
        } -> tensor<16x64xf32>
        iree_tensor_ext.dispatch.tensor.store %6, %arg3, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : tensor<16x64xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>
        return
      }
    }
  }
  flow.executable private @main_dispatch_1 {
    flow.executable.export public @main_dispatch_1_matmul_16x32x64_f32 workgroups() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    builtin.module {
      func.func @main_dispatch_1_matmul_16x32x64_f32(%arg0: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>>, %arg1: !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>>, %arg2: !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>>, %arg3: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg4: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>) {
        %cst = arith.constant 0.000000e+00 : f32
        %0 = iree_tensor_ext.dispatch.tensor.load %arg0, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>> -> tensor<16x64xf32>
        %1 = iree_tensor_ext.dispatch.tensor.load %arg1, offsets = [0, 0], sizes = [64, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>> -> tensor<64x32xf32>
        %2 = iree_tensor_ext.dispatch.tensor.load %arg2, offsets = [0], sizes = [32], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>> -> tensor<32xf32>
        %3 = iree_tensor_ext.dispatch.tensor.load %arg3, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
        %4 = tensor.empty() : tensor<16x32xf32>
        %5 = linalg.fill ins(%cst : f32) outs(%4 : tensor<16x32xf32>) -> tensor<16x32xf32>
        %6 = linalg.matmul ins(%0, %1 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%5 : tensor<16x32xf32>) -> tensor<16x32xf32>
        %7 = linalg.generic {indexing_maps = [#map, #map1, #map, #map], iterator_types = ["parallel", "parallel"]} ins(%6, %2, %3 : tensor<16x32xf32>, tensor<32xf32>, tensor<16x32xf32>) outs(%4 : tensor<16x32xf32>) {
        ^bb0(%in: f32, %in_0: f32, %in_1: f32, %out: f32):
          %8 = arith.addf %in, %in_0 : f32
          %9 = arith.addf %8, %in_1 : f32
          linalg.yield %9 : f32
        } -> tensor<16x32xf32>
        iree_tensor_ext.dispatch.tensor.store %7, %arg4, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : tensor<16x32xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
        return
      }
    }
  }
  flow.executable private @main_dispatch_2 {
    flow.executable.export public @main_dispatch_2_reduction_16x32_f32 workgroups() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    builtin.module {
      func.func @main_dispatch_2_reduction_16x32_f32(%arg0: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg1: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>) {
        %cst = arith.constant 0.000000e+00 : f32
        %0 = iree_tensor_ext.dispatch.tensor.load %arg0, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
        %1 = tensor.empty() : tensor<16xf32>
        %2 = linalg.fill ins(%cst : f32) outs(%1 : tensor<16xf32>) -> tensor<16xf32>
        %3 = linalg.generic {indexing_maps = [#map, #map2], iterator_types = ["parallel", "reduction"]} ins(%0 : tensor<16x32xf32>) outs(%2 : tensor<16xf32>) {
        ^bb0(%in: f32, %out: f32):
          %4 = arith.addf %out, %in : f32
          linalg.yield %4 : f32
        } -> tensor<16xf32>
        iree_tensor_ext.dispatch.tensor.store %3, %arg1, offsets = [0], sizes = [16], strides = [1] : tensor<16xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>
        return
      }
    }
  }
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %0 = hal.tensor.import %arg0 "input0" : !hal.buffer_view -> tensor<16x32xf32>
    %1 = hal.tensor.import %arg1 "input1" : !hal.buffer_view -> tensor<32x64xf32>
    %2 = hal.tensor.import %arg2 "input2" : !hal.buffer_view -> tensor<64xf32>
    %3 = hal.tensor.import %arg3 "input3" : !hal.buffer_view -> tensor<64x32xf32>
    %4 = hal.tensor.import %arg4 "input4" : !hal.buffer_view -> tensor<32xf32>
    %5 = hal.tensor.import %arg5 "input5" : !hal.buffer_view -> tensor<16x32xf32>
    %6 = flow.dispatch @main_dispatch_0::@main_dispatch_0_matmul_16x64x32_f32(%0, %1, %2) : (tensor<16x32xf32>, tensor<32x64xf32>, tensor<64xf32>) -> tensor<16x64xf32>
    %7 = flow.dispatch @main_dispatch_1::@main_dispatch_1_matmul_16x32x64_f32(%6, %3, %4, %5) : (tensor<16x64xf32>, tensor<64x32xf32>, tensor<32xf32>, tensor<16x32xf32>) -> tensor<16x32xf32>
    %8 = flow.dispatch @main_dispatch_2::@main_dispatch_2_reduction_16x32_f32(%7) : (tensor<16x32xf32>) -> tensor<16xf32>
    %9 = hal.tensor.export %7 "output0" : tensor<16x32xf32> -> !hal.buffer_view
    %10 = hal.tensor.export %8 "output1" : tensor<16xf32> -> !hal.buffer_view
    util.return %9, %10 : !hal.buffer_view, !hal.buffer_view
  }
}
