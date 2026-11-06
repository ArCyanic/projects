hal.executable public @main_dispatch_1 {
  hal.executable.variant public @metal_msl_fb target(<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>) {
    hal.executable.export public @main_dispatch_1_matmul_16x32x64_f32 ordinal(0) layout(#hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) count(%arg0: !hal.device) -> (index, index, index) {
      %x, %y, %z = iree_tensor_ext.dispatch.workgroup_count_from_slice()
      hal.return %x, %y, %z : index, index, index
    }
    builtin.module {
      func.func @main_dispatch_1_matmul_16x32x64_f32() {
        %cst = arith.constant 0.000000e+00 : f32
        %c0 = arith.constant 0 : index
        %0 = hal.interface.binding.subspan layout(<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) binding(0) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>>
        %1 = hal.interface.binding.subspan layout(<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) binding(1) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>>
        %2 = hal.interface.binding.subspan layout(<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) binding(2) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>>
        %3 = hal.interface.binding.subspan layout(<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) binding(3) alignment(64) offset(%c0) flags("ReadOnly|Indirect") : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>>
        %4 = hal.interface.binding.subspan layout(<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>) binding(4) alignment(64) offset(%c0) flags(Indirect) : !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
        %5 = iree_tensor_ext.dispatch.tensor.load %0, offsets = [0, 0], sizes = [16, 64], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x64xf32>> -> tensor<16x64xf32>
        %6 = iree_tensor_ext.dispatch.tensor.load %1, offsets = [0, 0], sizes = [64, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<64x32xf32>> -> tensor<64x32xf32>
        %7 = iree_tensor_ext.dispatch.tensor.load %2, offsets = [0], sizes = [32], strides = [1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<32xf32>> -> tensor<32xf32>
        %8 = iree_tensor_ext.dispatch.tensor.load %3, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : !iree_tensor_ext.dispatch.tensor<readonly:tensor<16x32xf32>> -> tensor<16x32xf32>
        %9 = tensor.empty() : tensor<16x32xf32>
        %10 = linalg.fill ins(%cst : f32) outs(%9 : tensor<16x32xf32>) -> tensor<16x32xf32>
        %11 = linalg.matmul ins(%5, %6 : tensor<16x64xf32>, tensor<64x32xf32>) outs(%10 : tensor<16x32xf32>) -> tensor<16x32xf32>
        %12 = linalg.generic {indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>, affine_map<(d0, d1) -> (d1)>, affine_map<(d0, d1) -> (d0, d1)>, affine_map<(d0, d1) -> (d0, d1)>], iterator_types = ["parallel", "parallel"]} ins(%11, %7, %8 : tensor<16x32xf32>, tensor<32xf32>, tensor<16x32xf32>) outs(%9 : tensor<16x32xf32>) {
        ^bb0(%in: f32, %in_0: f32, %in_1: f32, %out: f32):
          %13 = arith.addf %in, %in_0 : f32
          %14 = arith.addf %13, %in_1 : f32
          linalg.yield %14 : f32
        } -> tensor<16x32xf32>
        iree_tensor_ext.dispatch.tensor.store %12, %4, offsets = [0, 0], sizes = [16, 32], strides = [1, 1] : tensor<16x32xf32> -> !iree_tensor_ext.dispatch.tensor<writeonly:tensor<16x32xf32>>
        return
      }
    }
  }
}
