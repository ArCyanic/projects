module @residual_mlp attributes {vm.toplevel} {
  vm.module public @residual_mlp {
    vm.global.ref private mutable @__device_0 : !vm.ref<!hal.device>
    vm.global.ref private mutable @__device_0_executable_0_main_dispatch_0 : !vm.ref<!hal.executable>
    vm.global.ref private mutable @__device_0_executable_1_main_dispatch_1 : !vm.ref<!hal.executable>
    vm.global.ref private mutable @__device_0_executable_2_main_dispatch_2 : !vm.ref<!hal.executable>
    vm.global.ref private mutable @__main_memoize_result_0_device_0 : !vm.ref<!hal.command_buffer>
    vm.rodata private @_utf8_hal_device_id_C6650FF277232B5A {alignment = 1 : i64} "hal.device.id"
    vm.rodata private @_utf8_metal_B7639FCB614B0986 {alignment = 1 : i64} "metal"
    vm.rodata private @_utf8_hal_executable_format_E03EECB63A2AAF52 {alignment = 1 : i64} "hal.executable.format"
    vm.rodata private @_utf8_metal_msl_fb_2A69558F2095460D {alignment = 1 : i64} "metal-msl-fb"
    vm.rodata private @main_dispatch_0_metal_msl_fb {alignment = 16 : i64, mime_type = "application/x-flatbuffers"} dense<"0x4D544C3100000000EC070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C310000000044F8FFFF080000001801000001000000040000004AF8FFFF40000000100000001000000001000000080000005400000004000000010000000000000001000000000000000100000000000000000000000000000000000000230000006D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333200C4F8FFFF7400000004000000D0F8FFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F302E6D6C697200000000230000006D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333200010000000400000064F9FFFF0400000074F9FFFF00000300040000007A06000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F360A7B0A20202020666C6F617434205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F325F205B5B69642832295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F335F205B5B69642833295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F305F6D61746D756C5F31367836347833325F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F617434205F33363B0A202020205F3336203D20666C6F61743428302E30293B0A20202020666C6F617434205F33313B0A20202020666F72202875696E74205F3335203D2030753B20696E74285F333529203C20696E7428333275293B20290A202020207B0A202020202020202075696E74205F3430203D205F3335202F2034753B0A202020202020202075696E74205F3431203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A20387529202B205F34303B0A202020202020202075696E74205F3435203D205F3335202A203136753B0A202020202020202075696E74205F3436203D205F3435202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A2020202020202020666C6F617434205F3730203D20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E77292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203438755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E7A292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203332755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E79292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3436202B203136755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34315D2E78292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F34365D2C205F3336292929293B0A20202020202020205F3331203D205F37303B0A20202020202020205F3335202B3D2034753B0A20202020202020205F3336203D205F37303B0A2020202020202020636F6E74696E75653B0A202020207D0A20202020666C6F617434205F3735203D205F3331202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F325F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E785D3B0A20202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F335F292E5F6D305B28676C5F4C6F63616C496E766F636174696F6E49442E79202A2031367529202B20676C5F4C6F63616C496E766F636174696F6E49442E785D203D2073656C6563742873656C65637428666173743A3A6D6178285F37352C20666C6F61743428302E3029292C205F37352C2069736E616E285F373529292C20666C6F61743428302E30292C2069736E616E28666C6F61743428302E302929293B0A7D0A0A000008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<2092xi8>
    vm.rodata private @main_dispatch_1_metal_msl_fb {alignment = 16 : i64, mime_type = "application/x-flatbuffers"} dense<"0x4D544C3100000000F4070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C31000000003CF8FFFF080000001C010000010000000400000042F8FFFF4400000008000000100000000100000008000000580000000500000001000000000000000100000000000000010000000000000001000000000000000000000000000000230000006D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333200C0F8FFFF7400000004000000CCF8FFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F312E6D6C697200000000230000006D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333200010000000400000060F9FFFF0400000070F9FFFF00000300040000007E06000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F360A7B0A20202020666C6F617434205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F325F205B5B69642832295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F335F205B5B69642833295D5D3B0A20202020646576696365205F362A205F7265736F757263655F7661725F305F345F205B5B69642834295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F315F6D61746D756C5F31367833327836345F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F617434205F33373B0A202020205F3337203D20666C6F61743428302E30293B0A20202020666C6F617434205F33323B0A20202020666F72202875696E74205F3336203D2030753B20696E74285F333629203C20696E7428363475293B20290A202020207B0A202020202020202075696E74205F3431203D205F3336202F2034753B0A202020202020202075696E74205F3432203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A2031367529202B205F34313B0A202020202020202075696E74205F3436203D205F3336202A2038753B0A202020202020202075696E74205F3437203D205F3436202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A2020202020202020666C6F617434205F3731203D20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E77292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B203234755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E7A292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B203136755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E79292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F3437202B2038755D2C20666D6128666C6F61743428282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B5F34325D2E78292C20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B5F34375D2C205F3337292929293B0A20202020202020205F3332203D205F37313B0A20202020202020205F3336202B3D2034753B0A20202020202020205F3337203D205F37313B0A2020202020202020636F6E74696E75653B0A202020207D0A2020202075696E74205F3737203D2028676C5F4C6F63616C496E766F636174696F6E49442E79202A20387529202B20676C5F4C6F63616C496E766F636174696F6E49442E783B0A20202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F345F292E5F6D305B5F37375D203D20285F3332202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F325F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E785D29202B20282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F335F292E5F6D305B5F37375D3B0A7D0A0A000008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<2100xi8>
    vm.rodata private @main_dispatch_2_metal_msl_fb {alignment = 16 : i64, mime_type = "application/x-flatbuffers"} dense<"0x4D544C310000000044040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000C0000004D544C3100000000ECFBFFFF08000000080100000100000004000000F2FBFFFF300000002000000001000000010000000800000044000000020000000100000000000000000000000000000000000000230000006D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F663332005CFCFFFF740000000400000068FCFFFF080000000300000058000000646F632F697265652D73747564792F6E61746976652D31322D7374616765732F65786563757461626C65732F636F6E666967757265645F726573696475616C5F6D6C705F6D61696E5F64697370617463685F322E6D6C697200000000230000006D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F663332000100000004000000FCFCFFFF040000000CFDFFFF0000030004000000E302000023696E636C756465203C6D6574616C5F7374646C69623E0A23696E636C756465203C73696D642F73696D642E683E0A0A7573696E67206E616D657370616365206D6574616C3B0A0A737472756374205F370A7B0A20202020666C6F6174205F6D305B315D3B0A7D3B0A0A7374727563742073707644657363726970746F72536574427566666572300A7B0A20202020646576696365205F372A205F7265736F757263655F7661725F305F305F205B5B69642830295D5D3B0A20202020646576696365205F372A205F7265736F757263655F7661725F305F315F205B5B69642831295D5D3B0A7D3B0A0A6B65726E656C20766F6964206D61696E5F64697370617463685F325F726564756374696F6E5F31367833325F66333228636F6E7374616E742073707644657363726970746F7253657442756666657230262073707644657363726970746F7253657430205B5B6275666665722830295D5D2C2075696E743320676C5F576F726B47726F75704944205B5B74687265616467726F75705F706F736974696F6E5F696E5F677269645D5D2C2075696E743320676C5F4C6F63616C496E766F636174696F6E4944205B5B7468726561645F706F736974696F6E5F696E5F74687265616467726F75705D5D290A7B0A20202020666C6F6174205F3332203D2073696D645F73756D28282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F305F292E5F6D305B676C5F4C6F63616C496E766F636174696F6E49442E78202B2028676C5F576F726B47726F757049442E78202A20333275295D202B20302E30293B0A2020202069662028676C5F4C6F63616C496E766F636174696F6E49442E78203D3D203075290A202020207B0A2020202020202020282A73707644657363726970746F72536574302E5F7265736F757263655F7661725F305F315F292E5F6D305B676C5F576F726B47726F757049442E78202B20353132755D203D205F3332202B20302E303B0A202020207D0A7D0A0A0008000C000400080006000800040014001C00000004000000080000000000140018000000"> : vector<1156xi8>
    vm.func private @__main_memoize_apply() -> !vm.ref<!hal.command_buffer> attributes {inlining_policy = #util.inline.never, vm.unwind} {
      %c16 = vm.const.i32 16
      %c6 = vm.const.i32 6
      %c5 = vm.const.i32 5
      %c4 = vm.const.i32 4
      %c13 = vm.const.i32 13
      %c28 = vm.const.i32 28
      %c7 = vm.const.i32 7
      %c2 = vm.const.i32 2
      %null = vm.const.ref.zero : !vm.ref<!hal.buffer>
      %c1 = vm.const.i32 1
      %c8 = vm.const.i32 8
      %c3 = vm.const.i32 3
      %zero = vm.const.i32.zero
      %c2112 = vm.const.i64 2112
      %c128 = vm.const.i64 128
      %c4096 = vm.const.i64 4096
      %c256 = vm.const.i64 256
      %c8192 = vm.const.i64 8192
      %c2048 = vm.const.i64 2048
      %zero_0 = vm.const.i64.zero
      %c-1 = vm.const.i64 -1
      %__device_0 = vm.global.load.ref @__device_0 : !vm.ref<!hal.device>
      %__device_0_executable_0_main_dispatch_0 = vm.global.load.ref @__device_0_executable_0_main_dispatch_0 : !vm.ref<!hal.executable>
      %__device_0_executable_1_main_dispatch_1 = vm.global.load.ref @__device_0_executable_1_main_dispatch_1 : !vm.ref<!hal.executable>
      %__device_0_executable_2_main_dispatch_2 = vm.global.load.ref @__device_0_executable_2_main_dispatch_2 : !vm.ref<!hal.executable>
      %ref = vm.call @hal.command_buffer.create(%__device_0, %zero, %c3, %c-1, %c8) : (!vm.ref<!hal.device>, i32, i32, i64, i32) -> !vm.ref<!hal.command_buffer>
      vm.call.variadic @hal.command_buffer.dispatch(%ref, %__device_0_executable_0_main_dispatch_0, %zero, %c1, %c1, %c1, %zero_0, [], [(%zero, %zero, %null, %zero_0, %c2048), (%zero, %c1, %null, %zero_0, %c8192), (%zero, %c2, %null, %zero_0, %c256), (%zero, %c7, %null, %zero_0, %c4096)]) : (!vm.ref<!hal.command_buffer>, !vm.ref<!hal.executable>, i32, i32, i32, i32, i64, i32 ..., tuple<i32, i32, !vm.ref<!hal.buffer>, i64, i64> ...)
      vm.call @hal.command_buffer.execution_barrier(%ref, %c28, %c13, %zero_0) : (!vm.ref<!hal.command_buffer>, i32, i32, i64) -> ()
      vm.call.variadic @hal.command_buffer.dispatch(%ref, %__device_0_executable_1_main_dispatch_1, %zero, %c1, %c1, %c1, %zero_0, [], [(%zero, %c7, %null, %zero_0, %c4096), (%zero, %c3, %null, %zero_0, %c8192), (%zero, %c4, %null, %zero_0, %c128), (%zero, %c5, %null, %zero_0, %c2048), (%zero, %c6, %null, %zero_0, %c2112)]) : (!vm.ref<!hal.command_buffer>, !vm.ref<!hal.executable>, i32, i32, i32, i32, i64, i32 ..., tuple<i32, i32, !vm.ref<!hal.buffer>, i64, i64> ...)
      vm.call @hal.command_buffer.execution_barrier(%ref, %c28, %c13, %zero_0) : (!vm.ref<!hal.command_buffer>, i32, i32, i64) -> ()
      vm.call.variadic @hal.command_buffer.dispatch(%ref, %__device_0_executable_2_main_dispatch_2, %zero, %c16, %c1, %c1, %zero_0, [], [(%zero, %c6, %null, %zero_0, %c2112), (%zero, %c6, %null, %zero_0, %c2112)]) : (!vm.ref<!hal.command_buffer>, !vm.ref<!hal.executable>, i32, i32, i32, i32, i64, i32 ..., tuple<i32, i32, !vm.ref<!hal.buffer>, i64, i64> ...)
      vm.call @hal.command_buffer.execution_barrier(%ref, %c28, %c13, %zero_0) : (!vm.ref<!hal.command_buffer>, i32, i32, i64) -> ()
      vm.call @hal.command_buffer.finalize(%ref) : (!vm.ref<!hal.command_buffer>) -> ()
      vm.return %ref : !vm.ref<!hal.command_buffer>
    }
    vm.import private @hal.buffer.assert(%buffer : !vm.ref<!hal.buffer>, %message : !vm.buffer, %allocator : !vm.ref<!hal.allocator>, %minimum_length : i64, %memory_types : i32, %buffer_usage : i32)
    vm.import private @hal.buffer_view.create(%buffer : !vm.ref<!hal.buffer>, %source_offset : i64, %source_length : i64, %element_type : i32, %encoding_type : i32, %shape : i64 ...) -> !vm.ref<!hal.buffer_view> attributes {nosideeffects}
    vm.import private @hal.buffer_view.assert(%buffer_view : !vm.ref<!hal.buffer_view>, %message : !vm.buffer, %element_type : i32, %encoding_type : i32, %shape : i64 ...)
    vm.import private @hal.buffer_view.buffer(%buffer_view : !vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer> attributes {nosideeffects}
    vm.import private @hal.command_buffer.create(%device : !vm.ref<!hal.device>, %modes : i32, %command_categories : i32, %queue_affinity : i64, %binding_capacity : i32) -> !vm.ref<!hal.command_buffer> attributes {minimum_version = 6 : i32}
    vm.import private @hal.command_buffer.finalize(%command_buffer : !vm.ref<!hal.command_buffer>)
    vm.import private @hal.command_buffer.execution_barrier(%command_buffer : !vm.ref<!hal.command_buffer>, %source_stage_mask : i32, %target_stage_mask : i32, %flags : i64)
    vm.import private @hal.command_buffer.dispatch(%command_buffer : !vm.ref<!hal.command_buffer>, %executable : !vm.ref<!hal.executable>, %entry_point : i32, %workgroup_x : i32, %workgroup_y : i32, %workgroup_z : i32, %flags : i64, %constants : i32 ..., %bindings : tuple<i32, i32, !vm.ref<!hal.buffer>, i64, i64> ...)
    vm.import private @hal.device.allocator(%device : !vm.ref<!hal.device>) -> !vm.ref<!hal.allocator> attributes {nosideeffects}
    vm.import private @hal.device.query.i64(%device : !vm.ref<!hal.device>, %category : !vm.buffer, %key : !vm.buffer) -> (i32, i64) attributes {nosideeffects}
    vm.import private @hal.device.queue.alloca(%device : !vm.ref<!hal.device>, %queue_affinity : i64, %wait_fence : !vm.ref<!hal.fence>, %signal_fence : !vm.ref<!hal.fence>, %pool : i64, %memory_types : i32, %buffer_usage : i32, %allocation_size : i64, %flags : i64) -> !vm.ref<!hal.buffer>
    vm.import private @hal.device.queue.dealloca(%device : !vm.ref<!hal.device>, %queue_affinity : i64, %wait_fence : !vm.ref<!hal.fence>, %signal_fence : !vm.ref<!hal.fence>, %buffer : !vm.ref<!hal.buffer>, %flags : i64)
    vm.import private @hal.device.queue.execute.indirect(%device : !vm.ref<!hal.device>, %queue_affinity : i64, %wait_fence : !vm.ref<!hal.fence>, %signal_fence : !vm.ref<!hal.fence>, %command_buffer : !vm.ref<!hal.command_buffer>, %flags : i64, %binding_table : tuple<!vm.ref<!hal.buffer>, i64, i64> ...)
    vm.import private @hal.devices.count() -> i32 attributes {nosideeffects}
    vm.import private @hal.devices.get(%index : i32) -> !vm.ref<!hal.device> attributes {nosideeffects}
    vm.import private @hal.executable.create(%device : !vm.ref<!hal.device>, %queue_affinity : i64, %executable_format : !vm.buffer, %executable_data : !vm.buffer, %constants : !vm.buffer) -> !vm.ref<!hal.executable> attributes {nosideeffects}
    vm.import private @hal.fence.create(%device : !vm.ref<!hal.device>, %flags : i64) -> !vm.ref<!hal.fence>
    vm.import private @hal.fence.join(%flags : i64, %fences : !vm.ref<!hal.fence> ...) -> !vm.ref<!hal.fence> attributes {nosideeffects}
    vm.import private @hal.fence.await(%timeout_millis : i32, %flags : i64, %fences : !vm.ref<!hal.fence> ...) -> i32 attributes {vm.yield}
    vm.rodata private @_utf8_input0_DCE99660CEB3F6B {alignment = 1 : i64} "input0"
    vm.rodata private @_utf8_tensor_FC1814BC4A58F22A {alignment = 1 : i64} "tensor"
    vm.rodata private @_utf8_input1_B898B726583C85DA {alignment = 1 : i64} "input1"
    vm.rodata private @_utf8_input2_396EAC3FD425AA3E {alignment = 1 : i64} "input2"
    vm.rodata private @_utf8_input3_9D340A628A70AC6A {alignment = 1 : i64} "input3"
    vm.rodata private @_utf8_input4_1CF55AC2F2BC86A9 {alignment = 1 : i64} "input4"
    vm.rodata private @_utf8_input5_24EAB79EC8456F91 {alignment = 1 : i64} "input5"
    vm.func private @main(%arg0: !vm.ref<!hal.buffer_view>, %arg1: !vm.ref<!hal.buffer_view>, %arg2: !vm.ref<!hal.buffer_view>, %arg3: !vm.ref<!hal.buffer_view>, %arg4: !vm.ref<!hal.buffer_view>, %arg5: !vm.ref<!hal.buffer_view>) -> (!vm.ref<!hal.buffer_view>, !vm.ref<!hal.buffer_view>) attributes {iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}, vm.unwind, vm.yield} {
      %c16 = vm.const.i32 16
      %c1 = vm.const.i32 1
      %c553648160 = vm.const.i32 553648160
      %c3075 = vm.const.i32 3075
      %c48 = vm.const.i32 48
      %c16_0 = vm.const.i64 16
      %c32 = vm.const.i64 32
      %c64 = vm.const.i64 64
      %c2048 = vm.const.i64 2048
      %c8192 = vm.const.i64 8192
      %c256 = vm.const.i64 256
      %c128 = vm.const.i64 128
      %c4096 = vm.const.i64 4096
      %c2112 = vm.const.i64 2112
      %zero = vm.const.i64.zero
      %c-1 = vm.const.i64 -1
      %null = vm.const.ref.zero : !vm.ref<!hal.fence>
      %c-1_1 = vm.const.i32 -1
      %__device_0 = vm.global.load.ref @__device_0 : !vm.ref<!hal.device>
      %__main_memoize_result_0_device_0 = vm.global.load.ref @__main_memoize_result_0_device_0 : !vm.ref<!hal.command_buffer>
      %_utf8_input0_DCE99660CEB3F6B = vm.const.ref.rodata @_utf8_input0_DCE99660CEB3F6B : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg0, %_utf8_input0_DCE99660CEB3F6B, %c553648160, %c1, [%c16_0, %c32]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref = vm.call @hal.buffer_view.buffer(%arg0) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      %ref_2 = vm.call @hal.device.allocator(%__device_0) {nosideeffects} : (!vm.ref<!hal.device>) -> !vm.ref<!hal.allocator>
      %_utf8_tensor_FC1814BC4A58F22A = vm.const.ref.rodata @_utf8_tensor_FC1814BC4A58F22A : !vm.buffer
      vm.call @hal.buffer.assert(%ref, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c2048, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %_utf8_input1_B898B726583C85DA = vm.const.ref.rodata @_utf8_input1_B898B726583C85DA : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg1, %_utf8_input1_B898B726583C85DA, %c553648160, %c1, [%c32, %c64]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref_3 = vm.call @hal.buffer_view.buffer(%arg1) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      vm.call @hal.buffer.assert(%ref_3, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c8192, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %_utf8_input2_396EAC3FD425AA3E = vm.const.ref.rodata @_utf8_input2_396EAC3FD425AA3E : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg2, %_utf8_input2_396EAC3FD425AA3E, %c553648160, %c1, [%c64]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref_4 = vm.call @hal.buffer_view.buffer(%arg2) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      vm.call @hal.buffer.assert(%ref_4, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c256, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %_utf8_input3_9D340A628A70AC6A = vm.const.ref.rodata @_utf8_input3_9D340A628A70AC6A : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg3, %_utf8_input3_9D340A628A70AC6A, %c553648160, %c1, [%c64, %c32]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref_5 = vm.call @hal.buffer_view.buffer(%arg3) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      vm.call @hal.buffer.assert(%ref_5, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c8192, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %_utf8_input4_1CF55AC2F2BC86A9 = vm.const.ref.rodata @_utf8_input4_1CF55AC2F2BC86A9 : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg4, %_utf8_input4_1CF55AC2F2BC86A9, %c553648160, %c1, [%c32]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref_6 = vm.call @hal.buffer_view.buffer(%arg4) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      vm.call @hal.buffer.assert(%ref_6, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c128, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %_utf8_input5_24EAB79EC8456F91 = vm.const.ref.rodata @_utf8_input5_24EAB79EC8456F91 : !vm.buffer
      vm.call.variadic @hal.buffer_view.assert(%arg5, %_utf8_input5_24EAB79EC8456F91, %c553648160, %c1, [%c16_0, %c32]) : (!vm.ref<!hal.buffer_view>, !vm.buffer, i32, i32, i64 ...)
      %ref_7 = vm.call @hal.buffer_view.buffer(%arg5) {nosideeffects} : (!vm.ref<!hal.buffer_view>) -> !vm.ref<!hal.buffer>
      vm.call @hal.buffer.assert(%ref_7, %_utf8_tensor_FC1814BC4A58F22A, %ref_2, %c2048, %c16, %c3075) : (!vm.ref<!hal.buffer>, !vm.buffer, !vm.ref<!hal.allocator>, i64, i32, i32) -> ()
      %ref_8 = vm.call @hal.fence.create(%__device_0, %zero) : (!vm.ref<!hal.device>, i64) -> !vm.ref<!hal.fence>
      %ref_9 = vm.call @hal.device.queue.alloca(%__device_0, %c-1, %null, %ref_8, %zero, %c48, %c3075, %c2112, %zero) : (!vm.ref<!hal.device>, i64, !vm.ref<!hal.fence>, !vm.ref<!hal.fence>, i64, i32, i32, i64, i64) -> !vm.ref<!hal.buffer>
      %ref_10 = vm.call @hal.fence.create(%__device_0, %zero) : (!vm.ref<!hal.device>, i64) -> !vm.ref<!hal.fence>
      %ref_11 = vm.call @hal.device.queue.alloca(%__device_0, %c-1, %null, %ref_10, %zero, %c48, %c3075, %c4096, %zero) : (!vm.ref<!hal.device>, i64, !vm.ref<!hal.fence>, !vm.ref<!hal.fence>, i64, i32, i32, i64, i64) -> !vm.ref<!hal.buffer>
      %ref_12 = vm.call.variadic @hal.fence.join(%zero, [%ref_8, %ref_10]) {nosideeffects} : (i64, !vm.ref<!hal.fence> ...) -> !vm.ref<!hal.fence>
      %ref_13 = vm.call @hal.fence.create(%__device_0, %zero) : (!vm.ref<!hal.device>, i64) -> !vm.ref<!hal.fence>
      vm.call.variadic @hal.device.queue.execute.indirect(%__device_0, %c-1, %ref_12, %ref_13, %__main_memoize_result_0_device_0, %zero, [(%ref, %zero, %c2048), (%ref_3, %zero, %c8192), (%ref_4, %zero, %c256), (%ref_5, %zero, %c8192), (%ref_6, %zero, %c128), (%ref_7, %zero, %c2048), (%ref_9, %zero, %c2112), (%ref_11, %zero, %c4096)]) : (!vm.ref<!hal.device>, i64, !vm.ref<!hal.fence>, !vm.ref<!hal.fence>, !vm.ref<!hal.command_buffer>, i64, tuple<!vm.ref<!hal.buffer>, i64, i64> ...)
      %ref_14 = vm.call @hal.fence.create(%__device_0, %zero) : (!vm.ref<!hal.device>, i64) -> !vm.ref<!hal.fence>
      vm.call @hal.device.queue.dealloca(%__device_0, %c-1, %ref_13, %ref_14, %ref_11, %zero) : (!vm.ref<!hal.device>, i64, !vm.ref<!hal.fence>, !vm.ref<!hal.fence>, !vm.ref<!hal.buffer>, i64) -> ()
      vm.call.variadic.yieldable @hal.fence.await(%c-1_1, %zero, %ref_14) {segment_sizes = dense<[-1, -1, 1]> : vector<3xi16>, segment_types = [i32, i64, !vm.ref<!hal.fence>]} : (i32, i64, !vm.ref<!hal.fence>) -> ^bb1 (i32)
    ^bb1(%0: i32):  // pred: ^bb0
      vm.cond_br %0, ^bb3, ^bb2
    ^bb2:  // pred: ^bb1
      %ref_15 = vm.call.variadic @hal.buffer_view.create(%ref_9, %zero, %c2048, %c553648160, %c1, [%c16_0, %c32]) {nosideeffects} : (!vm.ref<!hal.buffer>, i64, i64, i32, i32, i64 ...) -> !vm.ref<!hal.buffer_view>
      %ref_16 = vm.call.variadic @hal.buffer_view.create(%ref_9, %c2048, %c64, %c553648160, %c1, [%c16_0]) {nosideeffects} : (!vm.ref<!hal.buffer>, i64, i64, i32, i32, i64 ...) -> !vm.ref<!hal.buffer_view>
      vm.return %ref_15, %ref_16 : !vm.ref<!hal.buffer_view>, !vm.ref<!hal.buffer_view>
    ^bb3:  // pred: ^bb1
      vm.discard.refs %ref_9 : !vm.ref<!hal.buffer>
      vm.fail %0, "failed to wait on timepoint"
    }
    vm.export @main attributes {iree.abi.stub, iree.reflection = {iree.abi.declaration = "sync func @main(%input0: tensor<16x32xf32>, %input1: tensor<32x64xf32>, %input2: tensor<64xf32>, %input3: tensor<64x32xf32>, %input4: tensor<32xf32>, %input5: tensor<16x32xf32>) -> (%output0: tensor<16x32xf32>, %output1: tensor<16xf32>)"}}
    vm.export @__init
    vm.func private @__init() attributes {vm.unwind} {
      %c1 = vm.const.i32 1
      %null = vm.const.ref.zero : !vm.buffer
      %c14 = vm.const.i32 14
      %c-1 = vm.const.i64 -1
      %c18 = vm.const.i32 18
      %zero = vm.const.i32.zero
      %zero_0 = vm.const.i64.zero
      %c1_1 = vm.const.i64 1
      %null_2 = vm.const.ref.zero : !vm.ref<!hal.device>
      %0 = vm.call @hal.devices.count() {nosideeffects} : () -> i32
      %1 = vm.ext.i32.i64.s %0 : i32 -> i64
      vm.br ^bb1(%zero_0, %zero_0, %null_2 : i64, i64, !vm.ref<!hal.device>)
    ^bb1(%2: i64, %3: i64, %4: !vm.ref<!hal.device>):  // 2 preds: ^bb0, ^bb4
      %rnz = vm.cmp.nz.ref %4 : !vm.ref<!hal.device>
      %5 = vm.xor.i32 %rnz, %c1 : i32
      %slt = vm.cmp.lt.i64.s %2, %1 : i64
      %6 = vm.and.i32 %5, %slt : i32
      vm.cond_br %6, ^bb2, ^bb5
    ^bb2:  // pred: ^bb1
      vm.discard.refs %4 : !vm.ref<!hal.device>
      %7 = vm.trunc.i64.i32 %2 : i64 -> i32
      %ref = vm.call @hal.devices.get(%7) {nosideeffects} : (i32) -> !vm.ref<!hal.device>
      %_utf8_hal_device_id_C6650FF277232B5A = vm.const.ref.rodata @_utf8_hal_device_id_C6650FF277232B5A : !vm.buffer
      %_utf8_metal_B7639FCB614B0986 = vm.const.ref.rodata @_utf8_metal_B7639FCB614B0986 : !vm.buffer
      %8:2 = vm.call @hal.device.query.i64(%ref, %_utf8_hal_device_id_C6650FF277232B5A, %_utf8_metal_B7639FCB614B0986) {nosideeffects} : (!vm.ref<!hal.device>, !vm.buffer, !vm.buffer) -> (i32, i64)
      %nz = vm.cmp.nz.i64 %8#1 : i64
      %9 = vm.select.i32 %8#0, %nz, %zero : i32
      vm.cond_br %9, ^bb3, ^bb4(%zero : i32)
    ^bb3:  // pred: ^bb2
      %_utf8_hal_executable_format_E03EECB63A2AAF52 = vm.const.ref.rodata @_utf8_hal_executable_format_E03EECB63A2AAF52 : !vm.buffer
      %_utf8_metal_msl_fb_2A69558F2095460D = vm.const.ref.rodata @_utf8_metal_msl_fb_2A69558F2095460D : !vm.buffer
      %10:2 = vm.call @hal.device.query.i64(%ref, %_utf8_hal_executable_format_E03EECB63A2AAF52, %_utf8_metal_msl_fb_2A69558F2095460D) {nosideeffects} : (!vm.ref<!hal.device>, !vm.buffer, !vm.buffer) -> (i32, i64)
      %nz_3 = vm.cmp.nz.i64 %10#1 : i64
      %11 = vm.select.i32 %10#0, %nz_3, %zero : i32
      vm.br ^bb4(%11 : i32)
    ^bb4(%12: i32):  // 2 preds: ^bb2, ^bb3
      %eq = vm.cmp.eq.i64 %3, %zero_0 : i64
      %13 = vm.select.i64 %12, %c1_1, %zero_0 : i64
      %14 = vm.add.i64 %3, %13 : i64
      %15 = vm.and.i32 %12, %eq : i32
      %ref_4 = vm.select.ref %15, %ref, %null_2 : !vm.ref<!hal.device>
      %16 = vm.add.i64 %2, %c1_1 : i64
      vm.br ^bb1(%16, %14, %ref_4 : i64, i64, !vm.ref<!hal.device>)
    ^bb5:  // pred: ^bb1
      vm.discard.refs %null_2 : !vm.ref<!hal.device>
      vm.cond_br %5, ^bb6, ^bb7
    ^bb6:  // pred: ^bb5
      vm.discard.refs %null, %4 : !vm.buffer, !vm.ref<!hal.device>
      vm.fail %c18, "HAL device `__device_0` not found or unavailable: #hal.device.target<\22metal\22, [#hal.executable.target<\22metal-spirv\22, \22metal-msl-fb\22, {iree_codegen.target_info = #iree_gpu.target<arch = \22apple\22, features = \22spirv:v1.3,cap:Shader\22, wgp = <compute = fp32|fp16|int64|int32|int16|int8, storage = b64|b32|b16|b8, subgroup = shuffle|arithmetic, dot = dp4xi8toi32, subgroup_size_choices = [32], max_workgroup_sizes = [1024, 1024, 1024], max_thread_count_per_workgroup = 1024, max_workgroup_memory_bytes = 32768, max_workgroup_counts = [65535, 65535, 65535]>>}>]>"
    ^bb7:  // pred: ^bb5
      %_utf8_hal_executable_format_E03EECB63A2AAF52_5 = vm.const.ref.rodata @_utf8_hal_executable_format_E03EECB63A2AAF52 : !vm.buffer
      %_utf8_metal_msl_fb_2A69558F2095460D_6 = vm.const.ref.rodata @_utf8_metal_msl_fb_2A69558F2095460D : !vm.buffer
      %17:2 = vm.call @hal.device.query.i64(%4, %_utf8_hal_executable_format_E03EECB63A2AAF52_5, %_utf8_metal_msl_fb_2A69558F2095460D_6) {nosideeffects} : (!vm.ref<!hal.device>, !vm.buffer, !vm.buffer) -> (i32, i64)
      %nz_7 = vm.cmp.nz.i64 %17#1 : i64
      %18 = vm.select.i32 %17#0, %nz_7, %zero : i32
      %19 = vm.select.i64 %18, %zero_0, %c-1 : i64
      %eq_8 = vm.cmp.eq.i64 %19, %zero_0 : i64
      vm.global.store.ref %4, @__device_0 : !vm.ref<!hal.device>
      vm.cond_br %eq_8, ^bb8, ^bb9
    ^bb8:  // pred: ^bb7
      %main_dispatch_0_metal_msl_fb = vm.const.ref.rodata @main_dispatch_0_metal_msl_fb : !vm.buffer
      %ref_9 = vm.call @hal.executable.create(%4, %c-1, %_utf8_metal_msl_fb_2A69558F2095460D_6, %main_dispatch_0_metal_msl_fb, %null) {nosideeffects} : (!vm.ref<!hal.device>, i64, !vm.buffer, !vm.buffer, !vm.buffer) -> !vm.ref<!hal.executable>
      vm.cond_br %eq_8, ^bb10, ^bb11
    ^bb9:  // pred: ^bb7
      vm.discard.refs %null, %4, %_utf8_metal_msl_fb_2A69558F2095460D_6 : !vm.buffer, !vm.ref<!hal.device>, !vm.buffer
      vm.fail %c14, "HAL device `__device_0` does not support any variant of executable `main_dispatch_0`; available formats: [metal-msl-fb]"
    ^bb10:  // pred: ^bb8
      %main_dispatch_1_metal_msl_fb = vm.const.ref.rodata @main_dispatch_1_metal_msl_fb : !vm.buffer
      %ref_10 = vm.call @hal.executable.create(%4, %c-1, %_utf8_metal_msl_fb_2A69558F2095460D_6, %main_dispatch_1_metal_msl_fb, %null) {nosideeffects} : (!vm.ref<!hal.device>, i64, !vm.buffer, !vm.buffer, !vm.buffer) -> !vm.ref<!hal.executable>
      vm.cond_br %eq_8, ^bb12, ^bb13
    ^bb11:  // pred: ^bb8
      vm.discard.refs %null, %4, %_utf8_metal_msl_fb_2A69558F2095460D_6, %ref_9 : !vm.buffer, !vm.ref<!hal.device>, !vm.buffer, !vm.ref<!hal.executable>
      vm.fail %c14, "HAL device `__device_0` does not support any variant of executable `main_dispatch_1`; available formats: [metal-msl-fb]"
    ^bb12:  // pred: ^bb10
      %main_dispatch_2_metal_msl_fb = vm.const.ref.rodata @main_dispatch_2_metal_msl_fb : !vm.buffer
      %ref_11 = vm.call @hal.executable.create(%4, %c-1, %_utf8_metal_msl_fb_2A69558F2095460D_6, %main_dispatch_2_metal_msl_fb, %null) {nosideeffects} : (!vm.ref<!hal.device>, i64, !vm.buffer, !vm.buffer, !vm.buffer) -> !vm.ref<!hal.executable>
      vm.global.store.ref %ref_9, @__device_0_executable_0_main_dispatch_0 : !vm.ref<!hal.executable>
      vm.global.store.ref %ref_10, @__device_0_executable_1_main_dispatch_1 : !vm.ref<!hal.executable>
      vm.global.store.ref %ref_11, @__device_0_executable_2_main_dispatch_2 : !vm.ref<!hal.executable>
      %ref_12 = vm.call @__main_memoize_apply() : () -> !vm.ref<!hal.command_buffer>
      vm.global.store.ref %ref_12, @__main_memoize_result_0_device_0 : !vm.ref<!hal.command_buffer>
      vm.return
    ^bb13:  // pred: ^bb10
      vm.discard.refs %null, %4, %_utf8_metal_msl_fb_2A69558F2095460D_6, %ref_9, %ref_10 : !vm.buffer, !vm.ref<!hal.device>, !vm.buffer, !vm.ref<!hal.executable>, !vm.ref<!hal.executable>
      vm.fail %c14, "HAL device `__device_0` does not support any variant of executable `main_dispatch_2`; available formats: [metal-msl-fb]"
    }
  }
}
