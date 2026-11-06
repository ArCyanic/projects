#executable_target_metal_msl_fb = #hal.executable.target<"metal-spirv", "metal-msl-fb", {iree_codegen.target_info = #iree_gpu.target<arch = "apple", features = "spirv:v1.3,cap:Shader", wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>
#pipeline_layout = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#pipeline_layout1 = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#pipeline_layout2 = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, "ReadOnly|Indirect">, #hal.pipeline.binding<storage_buffer, Indirect>], flags = Indirect>
#device_target_metal = #hal.device.target<"metal", [#executable_target_metal_msl_fb]> : !hal.device
module @residual_mlp attributes {stream.affinity.default = #hal.device.affinity<@__device_0>} {
  util.global private @__device_0 = #device_target_metal
  hal.executable private @main_dispatch_0 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_0_matmul_16x64x32_f32 ordinal(0) layout(#pipeline_layout) count(%arg0: !hal.device) -> (index, index, index) {
        %c1 = arith.constant 1 : index
        %c1_0 = arith.constant 1 : index
        %c1_1 = arith.constant 1 : index
        hal.return %c1, %c1_0, %c1_1 : index, index, index
      } attributes {workgroup_size = [16 : index, 16 : index, 1 : index]}
      builtin.module attributes {spirv.target_env = #spirv.target_env<#spirv.vce<v1.3, [Shader, Float16, Int64, Int16, Int8, StorageBuffer16BitAccess, StorageUniform16, StoragePushConstant16, StorageBuffer8BitAccess, UniformAndStorageBuffer8BitAccess, StoragePushConstant8, GroupNonUniformShuffle, GroupNonUniformShuffleRelative, GroupNonUniformArithmetic, DotProduct, DotProductInput4x8BitPacked, DotProductInputAll, DotProductInput4x8Bit], [SPV_KHR_16bit_storage, SPV_KHR_8bit_storage, SPV_KHR_integer_dot_product]>, Apple, #spirv.resource_limits<max_compute_shared_memory_size = 32768, max_compute_workgroup_invocations = 1024, max_compute_workgroup_size = [1024 : i32, 1024 : i32, 1024 : i32], min_subgroup_size = 32, max_subgroup_size = 32, cooperative_matrix_properties_khr = []>>} {
        spirv.module Logical GLSL450 requires #spirv.vce<v1.0, [Shader, Matrix], [SPV_KHR_storage_buffer_storage_class]> {
          spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
          spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_2_ bind(0, 2) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_3_ bind(0, 3) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.func @main_dispatch_0_matmul_16x64x32_f32() "None" {
            %cst16_i32 = spirv.Constant 16 : i32
            %cst48_i32 = spirv.Constant 48 : i32
            %cst8_i32 = spirv.Constant 8 : i32
            %cst4_i32 = spirv.Constant 4 : i32
            %cst32_i32 = spirv.Constant 32 : i32
            %cst0_i32 = spirv.Constant 0 : i32
            %cst_vec_4xf32 = spirv.Constant dense<0.000000e+00> : vector<4xf32>
            %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_2__addr = spirv.mlir.addressof @__resource_var_0_2_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_3__addr = spirv.mlir.addressof @__resource_var_0_3_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
            %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
            %1 = spirv.CompositeExtract %0[1 : i32] : vector<3xi32>
            %2 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
            %3 = spirv.CompositeExtract %2[0 : i32] : vector<3xi32>
            %4 = spirv.Variable : !spirv.ptr<vector<4xf32>, Function>
            spirv.mlir.loop {
              spirv.Branch ^bb1(%cst0_i32, %cst_vec_4xf32 : i32, vector<4xf32>)
            ^bb1(%17: i32, %18: vector<4xf32>):  // 2 preds: ^bb0, ^bb2
              %19 = spirv.SLessThan %17, %cst32_i32 : i32
              spirv.BranchConditional %19, ^bb2, ^bb3
            ^bb2:  // pred: ^bb1
              %20 = spirv.IMul %1, %cst8_i32 : i32
              %21 = spirv.UDiv %17, %cst4_i32 : i32
              %22 = spirv.IAdd %20, %21 : i32
              %23 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %22] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %24 = spirv.Load "StorageBuffer" %23 : vector<4xf32>
              %25 = spirv.IMul %17, %cst16_i32 : i32
              %26 = spirv.IAdd %25, %3 : i32
              %27 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %26] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %28 = spirv.Load "StorageBuffer" %27 : vector<4xf32>
              %29 = spirv.IAdd %26, %cst16_i32 : i32
              %30 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %29] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %31 = spirv.Load "StorageBuffer" %30 : vector<4xf32>
              %32 = spirv.IAdd %26, %cst32_i32 : i32
              %33 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %32] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %34 = spirv.Load "StorageBuffer" %33 : vector<4xf32>
              %35 = spirv.IAdd %26, %cst48_i32 : i32
              %36 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %35] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %37 = spirv.Load "StorageBuffer" %36 : vector<4xf32>
              %38 = spirv.CompositeExtract %24[0 : i32] : vector<4xf32>
              %39 = spirv.CompositeConstruct %38, %38, %38, %38 : (f32, f32, f32, f32) -> vector<4xf32>
              %40 = spirv.GL.Fma %39, %28, %18 : vector<4xf32>
              %41 = spirv.CompositeExtract %24[1 : i32] : vector<4xf32>
              %42 = spirv.CompositeConstruct %41, %41, %41, %41 : (f32, f32, f32, f32) -> vector<4xf32>
              %43 = spirv.GL.Fma %42, %31, %40 : vector<4xf32>
              %44 = spirv.CompositeExtract %24[2 : i32] : vector<4xf32>
              %45 = spirv.CompositeConstruct %44, %44, %44, %44 : (f32, f32, f32, f32) -> vector<4xf32>
              %46 = spirv.GL.Fma %45, %34, %43 : vector<4xf32>
              %47 = spirv.CompositeExtract %24[3 : i32] : vector<4xf32>
              %48 = spirv.CompositeConstruct %47, %47, %47, %47 : (f32, f32, f32, f32) -> vector<4xf32>
              %49 = spirv.GL.Fma %48, %37, %46 : vector<4xf32>
              spirv.Store "Function" %4, %49 : vector<4xf32>
              %50 = spirv.IAdd %17, %cst4_i32 : i32
              spirv.Branch ^bb1(%50, %49 : i32, vector<4xf32>)
            ^bb3:  // pred: ^bb1
              spirv.mlir.merge
            }
            %5 = spirv.Load "Function" %4 : vector<4xf32>
            %6 = spirv.AccessChain %__resource_var_0_2__addr[%cst0_i32, %3] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
            %7 = spirv.Load "StorageBuffer" %6 : vector<4xf32>
            %8 = spirv.FAdd %5, %7 : vector<4xf32>
            %9 = spirv.GL.FMax %8, %cst_vec_4xf32 : vector<4xf32>
            %10 = spirv.IsNan %8 : vector<4xf32>
            %11 = spirv.IsNan %cst_vec_4xf32 : vector<4xf32>
            %12 = spirv.Select %10, %8, %9 : vector<4xi1>, vector<4xf32>
            %13 = spirv.Select %11, %cst_vec_4xf32, %12 : vector<4xi1>, vector<4xf32>
            %14 = spirv.IMul %1, %cst16_i32 : i32
            %15 = spirv.IAdd %14, %3 : i32
            %16 = spirv.AccessChain %__resource_var_0_3__addr[%cst0_i32, %15] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
            spirv.Store "StorageBuffer" %16, %13 : vector<4xf32>
            spirv.Return
          }
          spirv.EntryPoint "GLCompute" @main_dispatch_0_matmul_16x64x32_f32, @__builtin__LocalInvocationId__
          spirv.ExecutionMode @main_dispatch_0_matmul_16x64x32_f32 "LocalSize", 16, 16, 1
        }
      }
    }
  }
  hal.executable private @main_dispatch_1 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_1_matmul_16x32x64_f32 ordinal(0) layout(#pipeline_layout1) count(%arg0: !hal.device) -> (index, index, index) {
        %c1 = arith.constant 1 : index
        %c1_0 = arith.constant 1 : index
        %c1_1 = arith.constant 1 : index
        hal.return %c1, %c1_0, %c1_1 : index, index, index
      } attributes {workgroup_size = [8 : index, 16 : index, 1 : index]}
      builtin.module attributes {spirv.target_env = #spirv.target_env<#spirv.vce<v1.3, [Shader, Float16, Int64, Int16, Int8, StorageBuffer16BitAccess, StorageUniform16, StoragePushConstant16, StorageBuffer8BitAccess, UniformAndStorageBuffer8BitAccess, StoragePushConstant8, GroupNonUniformShuffle, GroupNonUniformShuffleRelative, GroupNonUniformArithmetic, DotProduct, DotProductInput4x8BitPacked, DotProductInputAll, DotProductInput4x8Bit], [SPV_KHR_16bit_storage, SPV_KHR_8bit_storage, SPV_KHR_integer_dot_product]>, Apple, #spirv.resource_limits<max_compute_shared_memory_size = 32768, max_compute_workgroup_invocations = 1024, max_compute_workgroup_size = [1024 : i32, 1024 : i32, 1024 : i32], min_subgroup_size = 32, max_subgroup_size = 32, cooperative_matrix_properties_khr = []>>} {
        spirv.module Logical GLSL450 requires #spirv.vce<v1.0, [Shader, Matrix], [SPV_KHR_storage_buffer_storage_class]> {
          spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
          spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_2_ bind(0, 2) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_3_ bind(0, 3) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_4_ bind(0, 4) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
          spirv.func @main_dispatch_1_matmul_16x32x64_f32() "None" {
            %cst8_i32 = spirv.Constant 8 : i32
            %cst24_i32 = spirv.Constant 24 : i32
            %cst16_i32 = spirv.Constant 16 : i32
            %cst4_i32 = spirv.Constant 4 : i32
            %cst64_i32 = spirv.Constant 64 : i32
            %cst0_i32 = spirv.Constant 0 : i32
            %cst_vec_4xf32 = spirv.Constant dense<0.000000e+00> : vector<4xf32>
            %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_2__addr = spirv.mlir.addressof @__resource_var_0_2_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_3__addr = spirv.mlir.addressof @__resource_var_0_3_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__resource_var_0_4__addr = spirv.mlir.addressof @__resource_var_0_4_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
            %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
            %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
            %1 = spirv.CompositeExtract %0[1 : i32] : vector<3xi32>
            %2 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
            %3 = spirv.CompositeExtract %2[0 : i32] : vector<3xi32>
            %4 = spirv.Variable : !spirv.ptr<vector<4xf32>, Function>
            spirv.mlir.loop {
              spirv.Branch ^bb1(%cst0_i32, %cst_vec_4xf32 : i32, vector<4xf32>)
            ^bb1(%15: i32, %16: vector<4xf32>):  // 2 preds: ^bb0, ^bb2
              %17 = spirv.SLessThan %15, %cst64_i32 : i32
              spirv.BranchConditional %17, ^bb2, ^bb3
            ^bb2:  // pred: ^bb1
              %18 = spirv.IMul %1, %cst16_i32 : i32
              %19 = spirv.UDiv %15, %cst4_i32 : i32
              %20 = spirv.IAdd %18, %19 : i32
              %21 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %20] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %22 = spirv.Load "StorageBuffer" %21 : vector<4xf32>
              %23 = spirv.IMul %15, %cst8_i32 : i32
              %24 = spirv.IAdd %23, %3 : i32
              %25 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %24] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %26 = spirv.Load "StorageBuffer" %25 : vector<4xf32>
              %27 = spirv.IAdd %24, %cst8_i32 : i32
              %28 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %27] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %29 = spirv.Load "StorageBuffer" %28 : vector<4xf32>
              %30 = spirv.IAdd %24, %cst16_i32 : i32
              %31 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %30] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %32 = spirv.Load "StorageBuffer" %31 : vector<4xf32>
              %33 = spirv.IAdd %24, %cst24_i32 : i32
              %34 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %33] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
              %35 = spirv.Load "StorageBuffer" %34 : vector<4xf32>
              %36 = spirv.CompositeExtract %22[0 : i32] : vector<4xf32>
              %37 = spirv.CompositeConstruct %36, %36, %36, %36 : (f32, f32, f32, f32) -> vector<4xf32>
              %38 = spirv.GL.Fma %37, %26, %16 : vector<4xf32>
              %39 = spirv.CompositeExtract %22[1 : i32] : vector<4xf32>
              %40 = spirv.CompositeConstruct %39, %39, %39, %39 : (f32, f32, f32, f32) -> vector<4xf32>
              %41 = spirv.GL.Fma %40, %29, %38 : vector<4xf32>
              %42 = spirv.CompositeExtract %22[2 : i32] : vector<4xf32>
              %43 = spirv.CompositeConstruct %42, %42, %42, %42 : (f32, f32, f32, f32) -> vector<4xf32>
              %44 = spirv.GL.Fma %43, %32, %41 : vector<4xf32>
              %45 = spirv.CompositeExtract %22[3 : i32] : vector<4xf32>
              %46 = spirv.CompositeConstruct %45, %45, %45, %45 : (f32, f32, f32, f32) -> vector<4xf32>
              %47 = spirv.GL.Fma %46, %35, %44 : vector<4xf32>
              spirv.Store "Function" %4, %47 : vector<4xf32>
              %48 = spirv.IAdd %15, %cst4_i32 : i32
              spirv.Branch ^bb1(%48, %47 : i32, vector<4xf32>)
            ^bb3:  // pred: ^bb1
              spirv.mlir.merge
            }
            %5 = spirv.Load "Function" %4 : vector<4xf32>
            %6 = spirv.AccessChain %__resource_var_0_2__addr[%cst0_i32, %3] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
            %7 = spirv.Load "StorageBuffer" %6 : vector<4xf32>
            %8 = spirv.IMul %1, %cst8_i32 : i32
            %9 = spirv.IAdd %8, %3 : i32
            %10 = spirv.AccessChain %__resource_var_0_3__addr[%cst0_i32, %9] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
            %11 = spirv.Load "StorageBuffer" %10 : vector<4xf32>
            %12 = spirv.FAdd %5, %7 : vector<4xf32>
            %13 = spirv.FAdd %12, %11 : vector<4xf32>
            %14 = spirv.AccessChain %__resource_var_0_4__addr[%cst0_i32, %9] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
            spirv.Store "StorageBuffer" %14, %13 : vector<4xf32>
            spirv.Return
          }
          spirv.EntryPoint "GLCompute" @main_dispatch_1_matmul_16x32x64_f32, @__builtin__LocalInvocationId__
          spirv.ExecutionMode @main_dispatch_1_matmul_16x32x64_f32 "LocalSize", 8, 16, 1
        }
      }
    }
  }
  hal.executable private @main_dispatch_2 {
    hal.executable.variant public @metal_msl_fb target(#executable_target_metal_msl_fb) {
      hal.executable.export public @main_dispatch_2_reduction_16x32_f32 ordinal(0) layout(#pipeline_layout2) count(%arg0: !hal.device) -> (index, index, index) {
        %c16 = arith.constant 16 : index
        %c1 = arith.constant 1 : index
        %c1_0 = arith.constant 1 : index
        hal.return %c16, %c1, %c1_0 : index, index, index
      } attributes {workgroup_size = [32 : index, 1 : index, 1 : index]}
      builtin.module attributes {spirv.target_env = #spirv.target_env<#spirv.vce<v1.3, [Shader, Float16, Int64, Int16, Int8, StorageBuffer16BitAccess, StorageUniform16, StoragePushConstant16, StorageBuffer8BitAccess, UniformAndStorageBuffer8BitAccess, StoragePushConstant8, GroupNonUniformShuffle, GroupNonUniformShuffleRelative, GroupNonUniformArithmetic, DotProduct, DotProductInput4x8BitPacked, DotProductInputAll, DotProductInput4x8Bit], [SPV_KHR_16bit_storage, SPV_KHR_8bit_storage, SPV_KHR_integer_dot_product]>, Apple, #spirv.resource_limits<max_compute_shared_memory_size = 32768, max_compute_workgroup_invocations = 1024, max_compute_workgroup_size = [1024 : i32, 1024 : i32, 1024 : i32], min_subgroup_size = 32, max_subgroup_size = 32, cooperative_matrix_properties_khr = []>>} {
        spirv.module Logical GLSL450 requires #spirv.vce<v1.3, [Shader, GroupNonUniformArithmetic, Matrix, GroupNonUniform], [SPV_KHR_storage_buffer_storage_class]> {
          spirv.GlobalVariable @__builtin__WorkgroupId__ built_in("WorkgroupId") : !spirv.ptr<vector<3xi32>, Input>
          spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
          spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
          spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
          spirv.func @main_dispatch_2_reduction_16x32_f32() "None" {
            %cst512_i32 = spirv.Constant 512 : i32
            %cst32_i32 = spirv.Constant 32 : i32
            %cst0_i32 = spirv.Constant 0 : i32
            %cst_f32 = spirv.Constant 0.000000e+00 : f32
            %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
            %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>
            %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
            %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
            %1 = spirv.CompositeExtract %0[0 : i32] : vector<3xi32>
            %2 = spirv.IEqual %1, %cst0_i32 : i32
            %__builtin__WorkgroupId___addr = spirv.mlir.addressof @__builtin__WorkgroupId__ : !spirv.ptr<vector<3xi32>, Input>
            %3 = spirv.Load "Input" %__builtin__WorkgroupId___addr : vector<3xi32>
            %4 = spirv.CompositeExtract %3[0 : i32] : vector<3xi32>
            %5 = spirv.IMul %4, %cst32_i32 : i32
            %6 = spirv.IAdd %1, %5 : i32
            %7 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %6] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<f32, StorageBuffer>
            %8 = spirv.Load "StorageBuffer" %7 : f32
            %9 = spirv.FAdd %8, %cst_f32 : f32
            %10 = spirv.GroupNonUniformFAdd <Subgroup> <Reduce> %9 : f32 -> f32
            %11 = spirv.FAdd %10, %cst_f32 : f32
            spirv.mlir.selection {
              spirv.BranchConditional %2, ^bb1, ^bb2
            ^bb1:  // pred: ^bb0
              %12 = spirv.IAdd %4, %cst512_i32 : i32
              %13 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %12] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<f32, stride=4> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<f32, StorageBuffer>
              spirv.Store "StorageBuffer" %13, %11 : f32
              spirv.Branch ^bb2
            ^bb2:  // 2 preds: ^bb0, ^bb1
              spirv.mlir.merge
            }
            spirv.Return
          }
          spirv.EntryPoint "GLCompute" @main_dispatch_2_reduction_16x32_f32, @__builtin__LocalInvocationId__, @__builtin__WorkgroupId__
          spirv.ExecutionMode @main_dispatch_2_reduction_16x32_f32 "LocalSize", 32, 1, 1
        }
      }
    }
  }
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %c0 = arith.constant 0 : index
    %c2112 = arith.constant 2112 : index
    %c4096 = arith.constant 4096 : index
    %c128 = arith.constant 128 : index
    %c256 = arith.constant 256 : index
    %c8192 = arith.constant 8192 : index
    %c2048 = arith.constant 2048 : index
    %c64 = arith.constant 64 : index
    %c32 = arith.constant 32 : index
    %c16 = arith.constant 16 : index
    %element_type_f32 = hal.element_type<f32> : i32
    %dense_row_major = hal.encoding_type<dense_row_major> : i32
    hal.buffer_view.assert<%arg0 : !hal.buffer_view> message("input0") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %0 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg0 : !hal.buffer_view -> tensor<16x32xf32> in !stream.resource<external>{%c2048}
    hal.buffer_view.assert<%arg1 : !hal.buffer_view> message("input1") shape([%c32, %c64]) type(%element_type_f32) encoding(%dense_row_major)
    %1 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg1 : !hal.buffer_view -> tensor<32x64xf32> in !stream.resource<external>{%c8192}
    hal.buffer_view.assert<%arg2 : !hal.buffer_view> message("input2") shape([%c64]) type(%element_type_f32) encoding(%dense_row_major)
    %2 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg2 : !hal.buffer_view -> tensor<64xf32> in !stream.resource<external>{%c256}
    hal.buffer_view.assert<%arg3 : !hal.buffer_view> message("input3") shape([%c64, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %3 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg3 : !hal.buffer_view -> tensor<64x32xf32> in !stream.resource<external>{%c8192}
    hal.buffer_view.assert<%arg4 : !hal.buffer_view> message("input4") shape([%c32]) type(%element_type_f32) encoding(%dense_row_major)
    %4 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg4 : !hal.buffer_view -> tensor<32xf32> in !stream.resource<external>{%c128}
    hal.buffer_view.assert<%arg5 : !hal.buffer_view> message("input5") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %5 = stream.tensor.import on(#hal.device.affinity<@__device_0>) %arg5 : !hal.buffer_view -> tensor<16x32xf32> in !stream.resource<external>{%c2048}
    %result, %result_timepoint = stream.resource.alloca uninitialized on(#hal.device.affinity<@__device_0>) : !stream.resource<external>{%c2112} => !stream.timepoint
    %result_0, %result_timepoint_1 = stream.resource.alloca uninitialized on(#hal.device.affinity<@__device_0>) : !stream.resource<transient>{%c4096} => !stream.timepoint
    %6 = stream.timepoint.join max(%result_timepoint, %result_timepoint_1) => !stream.timepoint
    %7 = stream.cmd.execute on(#hal.device.affinity<@__device_0>) await(%6) => with(%0 as %arg6: !stream.resource<external>{%c2048}, %1 as %arg7: !stream.resource<external>{%c8192}, %2 as %arg8: !stream.resource<external>{%c256}, %3 as %arg9: !stream.resource<external>{%c8192}, %4 as %arg10: !stream.resource<external>{%c128}, %5 as %arg11: !stream.resource<external>{%c2048}, %result as %arg12: !stream.resource<external>{%c2112}, %result_0 as %arg13: !stream.resource<transient>{%c4096}) {
      stream.cmd.dispatch @main_dispatch_0::@metal_msl_fb::@main_dispatch_0_matmul_16x64x32_f32 {
        ro %arg6[%c0 for %c2048] : !stream.resource<external>{%c2048},
        ro %arg7[%c0 for %c8192] : !stream.resource<external>{%c8192},
        ro %arg8[%c0 for %c256] : !stream.resource<external>{%c256},
        wo %arg13[%c0 for %c4096] : !stream.resource<transient>{%c4096}
      }
      stream.cmd.dispatch @main_dispatch_1::@metal_msl_fb::@main_dispatch_1_matmul_16x32x64_f32 {
        ro %arg13[%c0 for %c4096] : !stream.resource<transient>{%c4096},
        ro %arg9[%c0 for %c8192] : !stream.resource<external>{%c8192},
        ro %arg10[%c0 for %c128] : !stream.resource<external>{%c128},
        ro %arg11[%c0 for %c2048] : !stream.resource<external>{%c2048},
        wo %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112}
      }
      stream.cmd.dispatch @main_dispatch_2::@metal_msl_fb::@main_dispatch_2_reduction_16x32_f32 {
        ro %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112},
        wo %arg12[%c0 for %c2112] : !stream.resource<external>{%c2112}
      }
    } => !stream.timepoint
    %8 = stream.resource.dealloca on(#hal.device.affinity<@__device_0>) await(%7) => %result_0 : !stream.resource<transient>{%c4096} => !stream.timepoint
    %9 = stream.timepoint.await %8 => %result : !stream.resource<external>{%c2112}
    %10 = stream.resource.subview %9[%c0] : !stream.resource<external>{%c2112} -> !stream.resource<external>{%c2048}
    %11 = stream.resource.subview %9[%c2048] : !stream.resource<external>{%c2112} -> !stream.resource<external>{%c64}
    %12 = stream.tensor.export on(#hal.device.affinity<@__device_0>) %10 : tensor<16x32xf32> in !stream.resource<external>{%c2048} -> !hal.buffer_view
    %13 = stream.tensor.export on(#hal.device.affinity<@__device_0>) %11 : tensor<16xf32> in !stream.resource<external>{%c64} -> !hal.buffer_view
    util.return %12, %13 : !hal.buffer_view, !hal.buffer_view
  }
}
