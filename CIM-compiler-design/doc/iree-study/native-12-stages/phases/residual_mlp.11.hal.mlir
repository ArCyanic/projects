module @residual_mlp {
  util.global private @__device_0 : !hal.device
  util.initializer {
    %c18_i32 = arith.constant 18 : i32
    %false = arith.constant false
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %0 = util.null : !hal.device
    %device_count = hal.devices.count : index
    cf.br ^bb1(%c0, %c0, %0 : index, index, !hal.device)
  ^bb1(%1: index, %2: index, %3: !hal.device):  // 2 preds: ^bb0, ^bb4
    %4 = util.cmp.eq %3, %0 : !hal.device
    %5 = arith.cmpi slt, %1, %device_count : index
    %6 = arith.andi %4, %5 : i1
    cf.cond_br %6, ^bb2, ^bb5
  ^bb2:  // pred: ^bb1
    %device_n = hal.devices.get %1 : !hal.device
    %ok, %value = hal.device.query<%device_n : !hal.device> key("hal.device.id" :: "metal") : i1, i1 = false
    cf.cond_br %value, ^bb3, ^bb4(%false : i1)
  ^bb3:  // pred: ^bb2
    %ok_0, %value_1 = hal.device.query<%device_n : !hal.device> key("hal.executable.format" :: "metal-msl-fb") : i1, i1 = false
    cf.br ^bb4(%value_1 : i1)
  ^bb4(%7: i1):  // 2 preds: ^bb2, ^bb3
    %8 = arith.cmpi eq, %2, %c0 : index
    %9 = arith.select %7, %c1, %c0 : index
    %10 = arith.addi %2, %9 : index
    %11 = arith.andi %7, %8 : i1
    %12 = arith.select %11, %device_n, %0 : !hal.device
    %13 = arith.addi %1, %c1 : index
    cf.br ^bb1(%13, %10, %12 : index, index, !hal.device)
  ^bb5:  // pred: ^bb1
    cf.cond_br %4, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    util.status.check_ok %c18_i32, "HAL device `__device_0` not found or unavailable: #hal.device.target<\22metal\22, [#hal.executable.target<\22metal-spirv\22, \22metal-msl-fb\22, {iree_codegen.target_info = #iree_gpu.target<arch = \22apple\22, features = \22spirv:v1.3,cap:Shader\22, wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>]>"
    cf.br ^bb7
  ^bb7:  // 2 preds: ^bb5, ^bb6
    util.global.store %3, @__device_0 : !hal.device
    util.return
  }
  util.global private @__device_0_query_0_hal_executable_format_metal_msl_fb : i1
  util.initializer {
    %__device_0 = util.global.load @__device_0 : !hal.device
    %ok, %value = hal.device.query<%__device_0 : !hal.device> key("hal.executable.format" :: "metal-msl-fb") : i1, i1 = false
    util.global.store %value, @__device_0_query_0_hal_executable_format_metal_msl_fb : i1
    util.return
  }
  util.global private @__device_0_executable_0_main_dispatch_0 : !hal.executable
  util.global private @__device_0_executable_1_main_dispatch_1 : !hal.executable
  util.global private @__device_0_executable_2_main_dispatch_2 : !hal.executable
  util.initializer {
    %c-1_i64 = arith.constant -1 : i64
    %c-1 = arith.constant -1 : index
    %c0 = arith.constant 0 : index
    %c14_i32 = arith.constant 14 : i32
    %0 = util.null : !hal.executable
    %__device_0_query_0_hal_executable_format_metal_msl_fb = util.global.load @__device_0_query_0_hal_executable_format_metal_msl_fb : i1
    %__device_0 = util.global.load @__device_0 : !hal.device
    %1 = arith.select %__device_0_query_0_hal_executable_format_metal_msl_fb, %c0, %c-1 : index
    %2 = arith.cmpi eq, %1, %c0 : index
    cf.cond_br %2, ^bb1, ^bb2
  ^bb1:  // pred: ^bb0
    %executable = hal.executable.create device(%__device_0 : !hal.device) affinity(%c-1_i64) target(@main_dispatch_0::@metal_msl_fb) : !hal.executable
    cf.br ^bb3(%executable : !hal.executable)
  ^bb2:  // pred: ^bb0
    util.status.check_ok %c14_i32, "HAL device `__device_0` does not support any variant of executable `main_dispatch_0`; available formats: [metal-msl-fb]"
    cf.br ^bb3(%0 : !hal.executable)
  ^bb3(%3: !hal.executable):  // 2 preds: ^bb1, ^bb2
    cf.cond_br %2, ^bb4, ^bb5
  ^bb4:  // pred: ^bb3
    %executable_0 = hal.executable.create device(%__device_0 : !hal.device) affinity(%c-1_i64) target(@main_dispatch_1::@metal_msl_fb) : !hal.executable
    cf.br ^bb6(%executable_0 : !hal.executable)
  ^bb5:  // pred: ^bb3
    util.status.check_ok %c14_i32, "HAL device `__device_0` does not support any variant of executable `main_dispatch_1`; available formats: [metal-msl-fb]"
    cf.br ^bb6(%0 : !hal.executable)
  ^bb6(%4: !hal.executable):  // 2 preds: ^bb4, ^bb5
    cf.cond_br %2, ^bb7, ^bb8
  ^bb7:  // pred: ^bb6
    %executable_1 = hal.executable.create device(%__device_0 : !hal.device) affinity(%c-1_i64) target(@main_dispatch_2::@metal_msl_fb) : !hal.executable
    cf.br ^bb9(%executable_1 : !hal.executable)
  ^bb8:  // pred: ^bb6
    util.status.check_ok %c14_i32, "HAL device `__device_0` does not support any variant of executable `main_dispatch_2`; available formats: [metal-msl-fb]"
    cf.br ^bb9(%0 : !hal.executable)
  ^bb9(%5: !hal.executable):  // 2 preds: ^bb7, ^bb8
    util.global.store %3, @__device_0_executable_0_main_dispatch_0 : !hal.executable
    util.global.store %4, @__device_0_executable_1_main_dispatch_1 : !hal.executable
    util.global.store %5, @__device_0_executable_2_main_dispatch_2 : !hal.executable
    util.return
  }
  hal.executable private @main_dispatch_0 {
    hal.executable.binary public @metal_msl_fb attributes {data = dense<"0x4D544C3100000000EC070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C310000000044F8FFFF080000001801000001000000040000004AF8FFFF40000000100000001000000001000000080000005400000004000000010000000000000001000000000000000100000000000000000000000000000000000000230000006D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333200C4F8FFFF7400000004000000D0F8FFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F302E6D6C697200000000230000006D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333200010000000400000064F9FFFF0400000074F9FFFF00000300040000007A06000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F360A7B0A20202020666C6F617434205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F325F205B5B69642832295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F335F205B5B69642833295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F617434205F33363B0A202020205F3336203D20666C6F61743428302E30293B0A20202020666C6F617434205F33313B0A20202020666F72202875696E74205F3335203D2030753B20696E74285F333529203C20696E7428333275293B20290A202020207B0A202020202020202075696E74205F3430203D205F3335202F2034753B0A202020202020202075696E74205F3431203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A20387529202B205F34303B0A202020202020202075696E74205F3435203D205F3335202A203136753B0A202020202020202075696E74205F3436203D205F3435202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A2020202020202020666C6F617434205F3730203D20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E77292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203438755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E7A292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203332755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E79292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203136755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E78292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F34365D2C205F3336292929293B0A20202020202020205F3331203D205F37303B0A20202020202020205F3335202B3D2034753B0A20202020202020205F3336203D205F37303B0A2020202020202020636F6E74696E75653B0A202020207D0A20202020666C6F617434205F3735203D205F3331202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F325F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E785D3B0A20202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F335F292E5F6D305B28676C5F4C6F63616C496E766F636174696F6E49442E79202A2031367529202B20676C5F4C6F63616C496E766F636174696F6E49442E785D203D2073656C6563742873656C65637428666173743A3A6D6178285F37352C20666C6F61743428302E3029292C205F37352C2069736E616E285F373529292C20666C6F61743428302E30292C2069736E616E28666C6F61743428302E302929293B0A7D0A0A000008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<2092xi8>, format = "metal-msl-fb", mime_type = "application/x-flatbuffers"}
  }
  hal.executable private @main_dispatch_1 {
    hal.executable.binary public @metal_msl_fb attributes {data = dense<"0x4D544C3100000000F4070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C31000000003CF8FFFF080000001C010000010000000400000042F8FFFF4400000008000000100000000100000008000000580000000500000001000000000000000100000000000000010000000000000001000000000000000000000000000000230000006D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333200C0F8FFFF7400000004000000CCF8FFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F312E6D6C697200000000230000006D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333200010000000400000060F9FFFF0400000070F9FFFF00000300040000007E06000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F360A7B0A20202020666C6F617434205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F325F205B5B69642832295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F335F205B5B69642833295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F345F205B5B69642834295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F617434205F33373B0A202020205F3337203D20666C6F61743428302E30293B0A20202020666C6F617434205F33323B0A20202020666F72202875696E74205F3336203D2030753B20696E74285F333629203C20696E7428363475293B20290A202020207B0A202020202020202075696E74205F3431203D205F3336202F2034753B0A202020202020202075696E74205F3432203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A2031367529202B205F34313B0A202020202020202075696E74205F3436203D205F3336202A2038753B0A202020202020202075696E74205F3437203D205F3436202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A2020202020202020666C6F617434205F3731203D20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E77292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B203234755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E7A292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B203136755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E79292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B2038755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E78292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F34375D2C205F3337292929293B0A20202020202020205F3332203D205F37313B0A20202020202020205F3336202B3D2034753B0A20202020202020205F3337203D205F37313B0A2020202020202020636F6E74696E75653B0A202020207D0A2020202075696E74205F3737203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A20387529202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A20202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F345F292E5F6D305B5F37375D203D20285F3332202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F325F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E785D29202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F335F292E5F6D305B5F37375D3B0A7D0A0A000008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<2100xi8>, format = "metal-msl-fb", mime_type = "application/x-flatbuffers"}
  }
  hal.executable private @main_dispatch_2 {
    hal.executable.binary public @metal_msl_fb attributes {data = dense<"0x4D544C310000000044040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C3100000000ECFBFFFF08000000080100000100000004000000F2FBFFFF300000002000000001000000010000000800000044000000020000000100000000000000000000000000000000000000230000006D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F663332005CFCFFFF740000000400000068FCFFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F322E6D6C697200000000230000006D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F663332000100000004000000FCFCFFFF040000000CFDFFFF0000030004000000E302000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F370A7B0A20202020666C6F6174205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F372A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F372A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F576F726B47726F75704944205B5B74687265616467726F75705F706F736974696F6E5F696E5F677269645D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F6174205F3332203D2073696D645F73756D28282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E78202B2028676C5F576F726B47726F757049442E78202A20333275295D202B20302E30293B0A2020202069662028676C5F4C6F63616C496E766F636174696F6E49442E78203D3D203075290A202020207B0A2020202020202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B676C5F576F726B47726F757049442E78202B20353132755D203D205F3332202B20302E303B0A202020207D0A7D0A0A0008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<1156xi8>, format = "metal-msl-fb", mime_type = "application/x-flatbuffers"}
  }
  util.func private @__main_memoize_apply() -> !hal.command_buffer attributes {inlining_policy = #util.inline.never} {
    %c-1_i64 = arith.constant -1 : i64
    %c16 = arith.constant 16 : index
    %c8 = arith.constant 8 : index
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c7 = arith.constant 7 : index
    %c2048 = arith.constant 2048 : index
    %c8192 = arith.constant 8192 : index
    %c256 = arith.constant 256 : index
    %c4096 = arith.constant 4096 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c5 = arith.constant 5 : index
    %c6 = arith.constant 6 : index
    %c128 = arith.constant 128 : index
    %c2112 = arith.constant 2112 : index
    %__device_0 = util.global.load immutable @__device_0 : !hal.device
    %__device_0_executable_0_main_dispatch_0 = util.global.load immutable @__device_0_executable_0_main_dispatch_0 : !hal.executable
    %__device_0_executable_1_main_dispatch_1 = util.global.load immutable @__device_0_executable_1_main_dispatch_1 : !hal.executable
    %__device_0_executable_2_main_dispatch_2 = util.global.load immutable @__device_0_executable_2_main_dispatch_2 : !hal.executable
    %cmd = hal.command_buffer.create device(%__device_0 : !hal.device) mode("None") categories("Transfer|Dispatch") affinity(%c-1_i64) bindings(%c8) : !hal.command_buffer
    hal.command_buffer.dispatch<%cmd : !hal.command_buffer> target(%__device_0_executable_0_main_dispatch_0 : !hal.executable)[%c0] workgroups([%c1, %c1, %c1]) bindings([
      (%c0 : index)[%c0, %c2048], 
      (%c1 : index)[%c0, %c8192], 
      (%c2 : index)[%c0, %c256], 
      (%c7 : index)[%c0, %c4096]
    ]) flags("None")
    hal.command_buffer.execution_barrier<%cmd : !hal.command_buffer> source("Dispatch|Transfer|CommandRetire") target("CommandIssue|Dispatch|Transfer") flags("None")
    hal.command_buffer.dispatch<%cmd : !hal.command_buffer> target(%__device_0_executable_1_main_dispatch_1 : !hal.executable)[%c0] workgroups([%c1, %c1, %c1]) bindings([
      (%c7 : index)[%c0, %c4096], 
      (%c3 : index)[%c0, %c8192], 
      (%c4 : index)[%c0, %c128], 
      (%c5 : index)[%c0, %c2048], 
      (%c6 : index)[%c0, %c2112]
    ]) flags("None")
    hal.command_buffer.execution_barrier<%cmd : !hal.command_buffer> source("Dispatch|Transfer|CommandRetire") target("CommandIssue|Dispatch|Transfer") flags("None")
    hal.command_buffer.dispatch<%cmd : !hal.command_buffer> target(%__device_0_executable_2_main_dispatch_2 : !hal.executable)[%c0] workgroups([%c16, %c1, %c1]) bindings([
      (%c6 : index)[%c0, %c2112], 
      (%c6 : index)[%c0, %c2112]
    ]) flags("None")
    hal.command_buffer.execution_barrier<%cmd : !hal.command_buffer> source("Dispatch|Transfer|CommandRetire") target("CommandIssue|Dispatch|Transfer") flags("None")
    hal.command_buffer.finalize<%cmd : !hal.command_buffer>
    util.return %cmd : !hal.command_buffer
  }
  util.global private @__main_memoize_result_0_device_0 : !hal.command_buffer
  util.initializer {
    %0 = util.call @__main_memoize_apply() : () -> !hal.command_buffer
    util.global.store %0, @__main_memoize_result_0_device_0 : !hal.command_buffer
    util.return
  }
  util.func public @main(%arg0: !hal.buffer_view, %arg1: !hal.buffer_view, %arg2: !hal.buffer_view, %arg3: !hal.buffer_view, %arg4: !hal.buffer_view, %arg5: !hal.buffer_view) -> (!hal.buffer_view, !hal.buffer_view) attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}} {
    %c-1_i32 = arith.constant -1 : i32
    %c0_i64 = arith.constant 0 : i64
    %0 = util.null : !hal.fence
    %c-1_i64 = arith.constant -1 : i64
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
    %memory_type = hal.memory_type<"DeviceVisible|DeviceLocal"> : i32
    %buffer_usage = hal.buffer_usage<"TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage"> : i32
    %__device_0 = util.global.load immutable @__device_0 : !hal.device
    %__main_memoize_result_0_device_0 = util.global.load immutable @__main_memoize_result_0_device_0 : !hal.command_buffer
    %element_type_f32 = hal.element_type<f32> : i32
    %dense_row_major = hal.encoding_type<dense_row_major> : i32
    hal.buffer_view.assert<%arg0 : !hal.buffer_view> message("input0") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer = hal.buffer_view.buffer<%arg0 : !hal.buffer_view> : !hal.buffer
    %allocator = hal.device.allocator<%__device_0 : !hal.device> : !hal.allocator
    hal.buffer.assert<%buffer : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c2048) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    hal.buffer_view.assert<%arg1 : !hal.buffer_view> message("input1") shape([%c32, %c64]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer_0 = hal.buffer_view.buffer<%arg1 : !hal.buffer_view> : !hal.buffer
    hal.buffer.assert<%buffer_0 : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c8192) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    hal.buffer_view.assert<%arg2 : !hal.buffer_view> message("input2") shape([%c64]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer_1 = hal.buffer_view.buffer<%arg2 : !hal.buffer_view> : !hal.buffer
    hal.buffer.assert<%buffer_1 : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c256) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    hal.buffer_view.assert<%arg3 : !hal.buffer_view> message("input3") shape([%c64, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer_2 = hal.buffer_view.buffer<%arg3 : !hal.buffer_view> : !hal.buffer
    hal.buffer.assert<%buffer_2 : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c8192) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    hal.buffer_view.assert<%arg4 : !hal.buffer_view> message("input4") shape([%c32]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer_3 = hal.buffer_view.buffer<%arg4 : !hal.buffer_view> : !hal.buffer
    hal.buffer.assert<%buffer_3 : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c128) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    hal.buffer_view.assert<%arg5 : !hal.buffer_view> message("input5") shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major)
    %buffer_4 = hal.buffer_view.buffer<%arg5 : !hal.buffer_view> : !hal.buffer
    hal.buffer.assert<%buffer_4 : !hal.buffer> message("tensor") allocator(%allocator : !hal.allocator) minimum_length(%c2048) type(DeviceVisible) usage("TransferSource|TransferTarget|Transfer|DispatchStorageRead|DispatchStorageWrite|DispatchStorage")
    %fence = hal.fence.create device(%__device_0 : !hal.device) flags("None") : !hal.fence
    %transient_buffer = hal.device.queue.alloca<%__device_0 : !hal.device> affinity(%c-1_i64) wait(%0) signal(%fence) pool(%c0_i64) type(%memory_type) usage(%buffer_usage) flags("None") : !hal.buffer{%c2112}
    %fence_5 = hal.fence.create device(%__device_0 : !hal.device) flags("None") : !hal.fence
    %transient_buffer_6 = hal.device.queue.alloca<%__device_0 : !hal.device> affinity(%c-1_i64) wait(%0) signal(%fence_5) pool(%c0_i64) type(%memory_type) usage(%buffer_usage) flags("None") : !hal.buffer{%c4096}
    %fence_7 = hal.fence.join at([%fence, %fence_5]) flags("None") -> !hal.fence
    %fence_8 = hal.fence.create device(%__device_0 : !hal.device) flags("None") : !hal.fence
    hal.device.queue.execute.indirect<%__device_0 : !hal.device> affinity(%c-1_i64) wait(%fence_7) signal(%fence_8) commands(%__main_memoize_result_0_device_0) bindings([
      (%buffer : !hal.buffer)[%c0, %c2048], 
      (%buffer_0 : !hal.buffer)[%c0, %c8192], 
      (%buffer_1 : !hal.buffer)[%c0, %c256], 
      (%buffer_2 : !hal.buffer)[%c0, %c8192], 
      (%buffer_3 : !hal.buffer)[%c0, %c128], 
      (%buffer_4 : !hal.buffer)[%c0, %c2048], 
      (%transient_buffer : !hal.buffer)[%c0, %c2112], 
      (%transient_buffer_6 : !hal.buffer)[%c0, %c4096]
    ]) flags("None")
    %fence_9 = hal.fence.create device(%__device_0 : !hal.device) flags("None") : !hal.fence
    hal.device.queue.dealloca<%__device_0 : !hal.device> affinity(%c-1_i64) wait(%fence_8) signal(%fence_9) buffer(%transient_buffer_6 : !hal.buffer) flags("None")
    %status = hal.fence.await until([%fence_9]) timeout_millis(%c-1_i32) flags("None") : i32
    util.status.check_ok %status, "failed to wait on timepoint"
    %view = hal.buffer_view.create buffer(%transient_buffer : !hal.buffer)[%c0, %c2048] shape([%c16, %c32]) type(%element_type_f32) encoding(%dense_row_major) : !hal.buffer_view
    %view_10 = hal.buffer_view.create buffer(%transient_buffer : !hal.buffer)[%c2048, %c64] shape([%c16]) type(%element_type_f32) encoding(%dense_row_major) : !hal.buffer_view
    util.return %view, %view_10 : !hal.buffer_view, !hal.buffer_view
  }
}
