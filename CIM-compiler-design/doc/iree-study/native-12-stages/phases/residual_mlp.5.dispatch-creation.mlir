#executable_target_metal_msl_fb = #hal.executable.target<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>
#map = affine_map<(d0, d1) -> (d0, d1)>
#map1 = affine_map<(d0, d1) -> (d1)>
#map2 = affine_map<(d0, d1) -> (d0)>
#device_target_metal = #hal.device.target<"metal", [#executable_target_metal_msl_fb]> : !hal.device
module @residual_mlp attributes {stream.affinity.default = #hal.device.affinity<@__device_0>} {
  util.global private @__device_0 = #device_target_metal
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %0 = hal.tensor.import %arg0 "input0" : !hal.buffer_view -> tensor<16x32xf32>
    %1 = hal.tensor.import %arg1 "input1" : !hal.buffer_view -> tensor<32x64xf32>
    %2 = hal.tensor.import %arg2 "input2" : !hal.buffer_view -> tensor<64xf32>
    %3 = hal.tensor.import %arg3 "input3" : !hal.buffer_view -> tensor<64x32xf32>
    %4 = hal.tensor.import %arg4 "input4" : !hal.buffer_view -> tensor<32xf32>
    %5 = hal.tensor.import %arg5 "input5" : !hal.buffer_view -> tensor<16x32xf32>
    %6 = flow.dispatch.workgroups(%0, %1, %2) : (tensor<16x32xf32>, tensor<32x64xf32>, tensor<64xf32>) -> tensor<16x64xf32> =
        (%arg6: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg7: !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>>, %arg8: !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>>, %arg9: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>) {
      %cst = arith.constant 0.000000e+00 : f32
      %11 = iree_tensor_ext.dispatch.tensor.load %arg6, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
      %12 = iree_tensor_ext.dispatch.tensor.load %arg7, offsets = [0, 0], sizes = [32, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32x64xf32>> -> tensor<32x64xf32>
      %13 = iree_tensor_ext.dispatch.tensor.load %arg8, offsets = [0], sizes = [64], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64xf32>> -> tensor<64xf32>
      %14 = tensor.empty() : tensor<16x64xf32>
      %15 = linalg.fill ins(%cst : f32) outs(%14 : tensor<16x64xf32>) -> tensor<16x64xf32>
      %16 = linalg.matmul ins(%11, %12 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%15 : tensor<16x64xf32>) -> tensor<16x64xf32>
      %17 = linalg.generic {indexing_maps = [#map, #map1, #map], iterator_types = ["parallel", "parallel"]} ins(%16, %13 : tensor<16x64xf32>, tensor<64xf32>) outs(%14 : tensor<16x64xf32>) {
      ^bb0(%in: f32, %in_0: f32, %out: f32):
        %18 = arith.addf %in, %in_0 : f32
        %19 = arith.maximumf %18, %cst : f32
        linalg.yield %19 : f32
      } -> tensor<16x64xf32>
      iree_tensor_ext.dispatch.tensor.store %17, %arg9, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : tensor<16x64xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x64xf32>>
      flow.return
    } count() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    %7 = flow.dispatch.workgroups(%6, %3, %4, %5) : (tensor<16x64xf32>, tensor<64x32xf32>, tensor<32xf32>, tensor<16x32xf32>) -> tensor<16x32xf32> =
        (%arg6: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>>, %arg7: !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>>, %arg8: !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>>, %arg9: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg10: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>) {
      %cst = arith.constant 0.000000e+00 : f32
      %11 = iree_tensor_ext.dispatch.tensor.load %arg6, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>> -> tensor<16x64xf32>
      %12 = iree_tensor_ext.dispatch.tensor.load %arg7, offsets = [0, 0], sizes = [64, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>> -> tensor<64x32xf32>
      %13 = iree_tensor_ext.dispatch.tensor.load %arg8, offsets = [0], sizes = [32], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>> -> tensor<32xf32>
      %14 = iree_tensor_ext.dispatch.tensor.load %arg9, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
      %15 = tensor.empty() : tensor<16x32xf32>
      %16 = linalg.fill ins(%cst : f32) outs(%15 : tensor<16x32xf32>) -> tensor<16x32xf32>
      %17 = linalg.matmul ins(%11, %12 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%16 : tensor<16x32xf32>) -> tensor<16x32xf32>
      %18 = linalg.generic {indexing_maps = [#map, #map1, #map, #map], iterator_types = ["parallel", "parallel"]} ins(%17, %13, %14 : tensor<16x32xf32>, tensor<32xf32>, tensor<16x32xf32>) outs(%15 : tensor<16x32xf32>) {
      ^bb0(%in: f32, %in_0: f32, %in_1: f32, %out: f32):
        %19 = arith.addf %in, %in_0 : f32
        %20 = arith.addf %19, %in_1 : f32
        linalg.yield %20 : f32
      } -> tensor<16x32xf32>
      iree_tensor_ext.dispatch.tensor.store %18, %arg10, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : tensor<16x32xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
      flow.return
    } count() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    %8 = flow.dispatch.workgroups(%7) : (tensor<16x32xf32>) -> tensor<16xf32> =
        (%arg6: !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>, %arg7: !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>) {
      %cst = arith.constant 0.000000e+00 : f32
      %11 = iree_tensor_ext.dispatch.tensor.load %arg6, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
      %12 = tensor.empty() : tensor<16xf32>
      %13 = linalg.fill ins(%cst : f32) outs(%12 : tensor<16xf32>) -> tensor<16xf32>
      %14 = linalg.generic {indexing_maps = [#map, #map2], iterator_types = ["parallel", "reduction"]} ins(%11 : tensor<16x32xf32>) outs(%13 : tensor<16xf32>) {
      ^bb0(%in: f32, %out: f32):
        %15 = arith.addf %out, %in : f32
        linalg.yield %15 : f32
      } -> tensor<16xf32>
      iree_tensor_ext.dispatch.tensor.store %14, %arg7, offsets = [0], sizes = [16], strides = [1] : tensor<16xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16xf32>>
      flow.return
    } count() -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      flow.return %x, %y, %z : index, index, index
    }
    %9 = hal.tensor.export %7 "output0" : tensor<16x32xf32> -> !hal.buffer_view
    %10 = hal.tensor.export %8 "output1" : tensor<16xf32> -> !hal.buffer_view
    util.return %9, %10 : !hal.buffer_view, !hal.buffer_view
  }
}
