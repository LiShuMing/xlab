
./bin/simd1:     file format elf64-x86-64


Disassembly of section .init:

0000000000001000 <_init>:
    1000:	f3 0f 1e fa          	endbr64 
    1004:	48 83 ec 08          	sub    $0x8,%rsp
    1008:	48 8b 05 d9 2f 00 00 	mov    0x2fd9(%rip),%rax        # 3fe8 <__gmon_start__@Base>
    100f:	48 85 c0             	test   %rax,%rax
    1012:	74 02                	je     1016 <_init+0x16>
    1014:	ff d0                	call   *%rax
    1016:	48 83 c4 08          	add    $0x8,%rsp
    101a:	c3                   	ret    

Disassembly of section .plt:

0000000000001020 <.plt>:
    1020:	ff 35 5a 2f 00 00    	push   0x2f5a(%rip)        # 3f80 <_GLOBAL_OFFSET_TABLE_+0x8>
    1026:	f2 ff 25 5b 2f 00 00 	bnd jmp *0x2f5b(%rip)        # 3f88 <_GLOBAL_OFFSET_TABLE_+0x10>
    102d:	0f 1f 00             	nopl   (%rax)
    1030:	f3 0f 1e fa          	endbr64 
    1034:	68 00 00 00 00       	push   $0x0
    1039:	f2 e9 e1 ff ff ff    	bnd jmp 1020 <_init+0x20>
    103f:	90                   	nop
    1040:	f3 0f 1e fa          	endbr64 
    1044:	68 01 00 00 00       	push   $0x1
    1049:	f2 e9 d1 ff ff ff    	bnd jmp 1020 <_init+0x20>
    104f:	90                   	nop
    1050:	f3 0f 1e fa          	endbr64 
    1054:	68 02 00 00 00       	push   $0x2
    1059:	f2 e9 c1 ff ff ff    	bnd jmp 1020 <_init+0x20>
    105f:	90                   	nop
    1060:	f3 0f 1e fa          	endbr64 
    1064:	68 03 00 00 00       	push   $0x3
    1069:	f2 e9 b1 ff ff ff    	bnd jmp 1020 <_init+0x20>
    106f:	90                   	nop
    1070:	f3 0f 1e fa          	endbr64 
    1074:	68 04 00 00 00       	push   $0x4
    1079:	f2 e9 a1 ff ff ff    	bnd jmp 1020 <_init+0x20>
    107f:	90                   	nop
    1080:	f3 0f 1e fa          	endbr64 
    1084:	68 05 00 00 00       	push   $0x5
    1089:	f2 e9 91 ff ff ff    	bnd jmp 1020 <_init+0x20>
    108f:	90                   	nop
    1090:	f3 0f 1e fa          	endbr64 
    1094:	68 06 00 00 00       	push   $0x6
    1099:	f2 e9 81 ff ff ff    	bnd jmp 1020 <_init+0x20>
    109f:	90                   	nop
    10a0:	f3 0f 1e fa          	endbr64 
    10a4:	68 07 00 00 00       	push   $0x7
    10a9:	f2 e9 71 ff ff ff    	bnd jmp 1020 <_init+0x20>
    10af:	90                   	nop

Disassembly of section .plt.got:

00000000000010b0 <__cxa_finalize@plt>:
    10b0:	f3 0f 1e fa          	endbr64 
    10b4:	f2 ff 25 15 2f 00 00 	bnd jmp *0x2f15(%rip)        # 3fd0 <__cxa_finalize@GLIBC_2.2.5>
    10bb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

Disassembly of section .plt.sec:

00000000000010c0 <_ZNSo3putEc@plt>:
    10c0:	f3 0f 1e fa          	endbr64 
    10c4:	f2 ff 25 c5 2e 00 00 	bnd jmp *0x2ec5(%rip)        # 3f90 <_ZNSo3putEc@GLIBCXX_3.4>
    10cb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

00000000000010d0 <_ZNSo5flushEv@plt>:
    10d0:	f3 0f 1e fa          	endbr64 
    10d4:	f2 ff 25 bd 2e 00 00 	bnd jmp *0x2ebd(%rip)        # 3f98 <_ZNSo5flushEv@GLIBCXX_3.4>
    10db:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

00000000000010e0 <__cxa_atexit@plt>:
    10e0:	f3 0f 1e fa          	endbr64 
    10e4:	f2 ff 25 b5 2e 00 00 	bnd jmp *0x2eb5(%rip)        # 3fa0 <__cxa_atexit@GLIBC_2.2.5>
    10eb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

00000000000010f0 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@plt>:
    10f0:	f3 0f 1e fa          	endbr64 
    10f4:	f2 ff 25 ad 2e 00 00 	bnd jmp *0x2ead(%rip)        # 3fa8 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@GLIBCXX_3.4.9>
    10fb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001100 <_ZNKSt5ctypeIcE13_M_widen_initEv@plt>:
    1100:	f3 0f 1e fa          	endbr64 
    1104:	f2 ff 25 a5 2e 00 00 	bnd jmp *0x2ea5(%rip)        # 3fb0 <_ZNKSt5ctypeIcE13_M_widen_initEv@GLIBCXX_3.4.11>
    110b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001110 <_ZSt16__throw_bad_castv@plt>:
    1110:	f3 0f 1e fa          	endbr64 
    1114:	f2 ff 25 9d 2e 00 00 	bnd jmp *0x2e9d(%rip)        # 3fb8 <_ZSt16__throw_bad_castv@GLIBCXX_3.4>
    111b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001120 <_ZNSt8ios_base4InitC1Ev@plt>:
    1120:	f3 0f 1e fa          	endbr64 
    1124:	f2 ff 25 95 2e 00 00 	bnd jmp *0x2e95(%rip)        # 3fc0 <_ZNSt8ios_base4InitC1Ev@GLIBCXX_3.4>
    112b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001130 <_ZNSo9_M_insertIdEERSoT_@plt>:
    1130:	f3 0f 1e fa          	endbr64 
    1134:	f2 ff 25 8d 2e 00 00 	bnd jmp *0x2e8d(%rip)        # 3fc8 <_ZNSo9_M_insertIdEERSoT_@GLIBCXX_3.4.9>
    113b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

Disassembly of section .text:

0000000000001140 <main>:
    1140:	f3 0f 1e fa          	endbr64 
    1144:	4c 8d 54 24 08       	lea    0x8(%rsp),%r10
    1149:	48 83 e4 e0          	and    $0xffffffffffffffe0,%rsp
    114d:	41 ff 72 f8          	push   -0x8(%r10)
    1151:	31 c0                	xor    %eax,%eax
    1153:	48 8d 35 06 30 00 00 	lea    0x3006(%rip),%rsi        # 4160 <c>
    115a:	55                   	push   %rbp
    115b:	48 8d 15 3e 36 00 00 	lea    0x363e(%rip),%rdx        # 47a0 <a>
    1162:	48 8d 0d 17 33 00 00 	lea    0x3317(%rip),%rcx        # 4480 <b>
    1169:	48 89 e5             	mov    %rsp,%rbp
    116c:	41 56                	push   %r14
    116e:	41 55                	push   %r13
    1170:	41 54                	push   %r12
    1172:	41 52                	push   %r10
    1174:	53                   	push   %rbx
    1175:	48 83 ec 08          	sub    $0x8,%rsp
    1179:	c5 fd 28 0d 9f 0e 00 	vmovapd 0xe9f(%rip),%ymm1        # 2020 <_IO_stdin_used+0x20>
    1180:	00 
    1181:	c5 fd 28 05 b7 0e 00 	vmovapd 0xeb7(%rip),%ymm0        # 2040 <_IO_stdin_used+0x40>
    1188:	00 
    1189:	c5 fd 29 0d 0f 36 00 	vmovapd %ymm1,0x360f(%rip)        # 47a0 <a>
    1190:	00 
    1191:	c5 fd 29 05 27 36 00 	vmovapd %ymm0,0x3627(%rip)        # 47c0 <a+0x20>
    1198:	00 
    1199:	c5 fd 29 0d df 32 00 	vmovapd %ymm1,0x32df(%rip)        # 4480 <b>
    11a0:	00 
    11a1:	c5 fd 29 05 f7 32 00 	vmovapd %ymm0,0x32f7(%rip)        # 44a0 <b+0x20>
    11a8:	00 
    11a9:	c5 fd 28 0d af 0e 00 	vmovapd 0xeaf(%rip),%ymm1        # 2060 <_IO_stdin_used+0x60>
    11b0:	00 
    11b1:	c5 fd 28 05 c7 0e 00 	vmovapd 0xec7(%rip),%ymm0        # 2080 <_IO_stdin_used+0x80>
    11b8:	00 
    11b9:	c5 fd 29 0d 1f 36 00 	vmovapd %ymm1,0x361f(%rip)        # 47e0 <a+0x40>
    11c0:	00 
    11c1:	c5 fd 29 05 37 36 00 	vmovapd %ymm0,0x3637(%rip)        # 4800 <a+0x60>
    11c8:	00 
    11c9:	c5 fd 29 0d ef 32 00 	vmovapd %ymm1,0x32ef(%rip)        # 44c0 <b+0x40>
    11d0:	00 
    11d1:	c5 fd 29 05 07 33 00 	vmovapd %ymm0,0x3307(%rip)        # 44e0 <b+0x60>
    11d8:	00 
    11d9:	c5 fd 28 0d bf 0e 00 	vmovapd 0xebf(%rip),%ymm1        # 20a0 <_IO_stdin_used+0xa0>
    11e0:	00 
    11e1:	c5 fd 28 05 d7 0e 00 	vmovapd 0xed7(%rip),%ymm0        # 20c0 <_IO_stdin_used+0xc0>
    11e8:	00 
    11e9:	c5 fd 29 0d 2f 36 00 	vmovapd %ymm1,0x362f(%rip)        # 4820 <a+0x80>
    11f0:	00 
    11f1:	c5 fd 29 05 47 36 00 	vmovapd %ymm0,0x3647(%rip)        # 4840 <a+0xa0>
    11f8:	00 
    11f9:	c5 fd 29 0d ff 32 00 	vmovapd %ymm1,0x32ff(%rip)        # 4500 <b+0x80>
    1200:	00 
    1201:	c5 fd 29 05 17 33 00 	vmovapd %ymm0,0x3317(%rip)        # 4520 <b+0xa0>
    1208:	00 
    1209:	c5 fd 28 0d cf 0e 00 	vmovapd 0xecf(%rip),%ymm1        # 20e0 <_IO_stdin_used+0xe0>
    1210:	00 
    1211:	c5 fd 28 05 e7 0e 00 	vmovapd 0xee7(%rip),%ymm0        # 2100 <_IO_stdin_used+0x100>
    1218:	00 
    1219:	c5 fd 29 0d 3f 36 00 	vmovapd %ymm1,0x363f(%rip)        # 4860 <a+0xc0>
    1220:	00 
    1221:	c5 fd 29 05 57 36 00 	vmovapd %ymm0,0x3657(%rip)        # 4880 <a+0xe0>
    1228:	00 
    1229:	c5 fd 29 0d 0f 33 00 	vmovapd %ymm1,0x330f(%rip)        # 4540 <b+0xc0>
    1230:	00 
    1231:	c5 fd 29 05 27 33 00 	vmovapd %ymm0,0x3327(%rip)        # 4560 <b+0xe0>
    1238:	00 
    1239:	c5 fd 28 0d df 0e 00 	vmovapd 0xedf(%rip),%ymm1        # 2120 <_IO_stdin_used+0x120>
    1240:	00 
    1241:	c5 fd 28 05 f7 0e 00 	vmovapd 0xef7(%rip),%ymm0        # 2140 <_IO_stdin_used+0x140>
    1248:	00 
    1249:	c5 fd 29 0d 4f 36 00 	vmovapd %ymm1,0x364f(%rip)        # 48a0 <a+0x100>
    1250:	00 
    1251:	c5 fd 29 0d 27 33 00 	vmovapd %ymm1,0x3327(%rip)        # 4580 <b+0x100>
    1258:	00 
    1259:	c5 fd 28 0d ff 0e 00 	vmovapd 0xeff(%rip),%ymm1        # 2160 <_IO_stdin_used+0x160>
    1260:	00 
    1261:	c5 fd 29 05 57 36 00 	vmovapd %ymm0,0x3657(%rip)        # 48c0 <a+0x120>
    1268:	00 
    1269:	c5 fd 29 05 2f 33 00 	vmovapd %ymm0,0x332f(%rip)        # 45a0 <b+0x120>
    1270:	00 
    1271:	c5 fd 29 0d 67 36 00 	vmovapd %ymm1,0x3667(%rip)        # 48e0 <a+0x140>
    1278:	00 
    1279:	c5 fd 28 05 ff 0e 00 	vmovapd 0xeff(%rip),%ymm0        # 2180 <_IO_stdin_used+0x180>
    1280:	00 
    1281:	c5 fd 29 0d 37 33 00 	vmovapd %ymm1,0x3337(%rip)        # 45c0 <b+0x140>
    1288:	00 
    1289:	c5 fd 28 0d 0f 0f 00 	vmovapd 0xf0f(%rip),%ymm1        # 21a0 <_IO_stdin_used+0x1a0>
    1290:	00 
    1291:	c5 fd 29 05 67 36 00 	vmovapd %ymm0,0x3667(%rip)        # 4900 <a+0x160>
    1298:	00 
    1299:	c5 fd 29 05 3f 33 00 	vmovapd %ymm0,0x333f(%rip)        # 45e0 <b+0x160>
    12a0:	00 
    12a1:	c5 fd 29 0d 77 36 00 	vmovapd %ymm1,0x3677(%rip)        # 4920 <a+0x180>
    12a8:	00 
    12a9:	c5 fd 28 05 0f 0f 00 	vmovapd 0xf0f(%rip),%ymm0        # 21c0 <_IO_stdin_used+0x1c0>
    12b0:	00 
    12b1:	c5 fd 29 0d 47 33 00 	vmovapd %ymm1,0x3347(%rip)        # 4600 <b+0x180>
    12b8:	00 
    12b9:	c5 fd 28 0d 1f 0f 00 	vmovapd 0xf1f(%rip),%ymm1        # 21e0 <_IO_stdin_used+0x1e0>
    12c0:	00 
    12c1:	c5 fd 29 05 77 36 00 	vmovapd %ymm0,0x3677(%rip)        # 4940 <a+0x1a0>
    12c8:	00 
    12c9:	c5 fd 29 05 4f 33 00 	vmovapd %ymm0,0x334f(%rip)        # 4620 <b+0x1a0>
    12d0:	00 
    12d1:	c5 fd 29 0d 87 36 00 	vmovapd %ymm1,0x3687(%rip)        # 4960 <a+0x1c0>
    12d8:	00 
    12d9:	c5 fd 28 05 1f 0f 00 	vmovapd 0xf1f(%rip),%ymm0        # 2200 <_IO_stdin_used+0x200>
    12e0:	00 
    12e1:	c5 fd 29 0d 57 33 00 	vmovapd %ymm1,0x3357(%rip)        # 4640 <b+0x1c0>
    12e8:	00 
    12e9:	c5 fd 28 0d 2f 0f 00 	vmovapd 0xf2f(%rip),%ymm1        # 2220 <_IO_stdin_used+0x220>
    12f0:	00 
    12f1:	c5 fd 29 05 87 36 00 	vmovapd %ymm0,0x3687(%rip)        # 4980 <a+0x1e0>
    12f8:	00 
    12f9:	c5 fd 29 05 5f 33 00 	vmovapd %ymm0,0x335f(%rip)        # 4660 <b+0x1e0>
    1300:	00 
    1301:	c5 fd 29 0d 97 36 00 	vmovapd %ymm1,0x3697(%rip)        # 49a0 <a+0x200>
    1308:	00 
    1309:	c5 fd 28 05 2f 0f 00 	vmovapd 0xf2f(%rip),%ymm0        # 2240 <_IO_stdin_used+0x240>
    1310:	00 
    1311:	c5 fd 29 0d 67 33 00 	vmovapd %ymm1,0x3367(%rip)        # 4680 <b+0x200>
    1318:	00 
    1319:	c5 fd 28 0d 3f 0f 00 	vmovapd 0xf3f(%rip),%ymm1        # 2260 <_IO_stdin_used+0x260>
    1320:	00 
    1321:	c5 fd 29 05 97 36 00 	vmovapd %ymm0,0x3697(%rip)        # 49c0 <a+0x220>
    1328:	00 
    1329:	c5 fd 29 0d af 36 00 	vmovapd %ymm1,0x36af(%rip)        # 49e0 <a+0x240>
    1330:	00 
    1331:	c5 fd 29 05 67 33 00 	vmovapd %ymm0,0x3367(%rip)        # 46a0 <b+0x220>
    1338:	00 
    1339:	c5 fd 28 05 3f 0f 00 	vmovapd 0xf3f(%rip),%ymm0        # 2280 <_IO_stdin_used+0x280>
    1340:	00 
    1341:	c5 fd 29 0d 77 33 00 	vmovapd %ymm1,0x3377(%rip)        # 46c0 <b+0x240>
    1348:	00 
    1349:	c5 fd 29 05 af 36 00 	vmovapd %ymm0,0x36af(%rip)        # 4a00 <a+0x260>
    1350:	00 
    1351:	c5 fd 28 0d 47 0f 00 	vmovapd 0xf47(%rip),%ymm1        # 22a0 <_IO_stdin_used+0x2a0>
    1358:	00 
    1359:	c5 fd 29 05 7f 33 00 	vmovapd %ymm0,0x337f(%rip)        # 46e0 <b+0x260>
    1360:	00 
    1361:	c5 fd 28 05 57 0f 00 	vmovapd 0xf57(%rip),%ymm0        # 22c0 <_IO_stdin_used+0x2c0>
    1368:	00 
    1369:	c5 fd 29 0d af 36 00 	vmovapd %ymm1,0x36af(%rip)        # 4a20 <a+0x280>
    1370:	00 
    1371:	c5 fd 29 05 c7 36 00 	vmovapd %ymm0,0x36c7(%rip)        # 4a40 <a+0x2a0>
    1378:	00 
    1379:	c5 fd 29 0d 7f 33 00 	vmovapd %ymm1,0x337f(%rip)        # 4700 <b+0x280>
    1380:	00 
    1381:	c5 fd 29 05 97 33 00 	vmovapd %ymm0,0x3397(%rip)        # 4720 <b+0x2a0>
    1388:	00 
    1389:	c5 fd 28 0d 4f 0f 00 	vmovapd 0xf4f(%rip),%ymm1        # 22e0 <_IO_stdin_used+0x2e0>
    1390:	00 
    1391:	c5 fd 28 05 67 0f 00 	vmovapd 0xf67(%rip),%ymm0        # 2300 <_IO_stdin_used+0x300>
    1398:	00 
    1399:	c5 fd 29 0d bf 36 00 	vmovapd %ymm1,0x36bf(%rip)        # 4a60 <a+0x2c0>
    13a0:	00 
    13a1:	c5 fd 29 05 d7 36 00 	vmovapd %ymm0,0x36d7(%rip)        # 4a80 <a+0x2e0>
    13a8:	00 
    13a9:	c5 fd 29 0d 8f 33 00 	vmovapd %ymm1,0x338f(%rip)        # 4740 <b+0x2c0>
    13b0:	00 
    13b1:	c5 fd 29 05 a7 33 00 	vmovapd %ymm0,0x33a7(%rip)        # 4760 <b+0x2e0>
    13b8:	00 
    13b9:	c5 f9 28 0d 5f 0f 00 	vmovapd 0xf5f(%rip),%xmm1        # 2320 <_IO_stdin_used+0x320>
    13c0:	00 
    13c1:	c5 f9 28 05 67 0f 00 	vmovapd 0xf67(%rip),%xmm0        # 2330 <_IO_stdin_used+0x330>
    13c8:	00 
    13c9:	c5 f9 29 0d cf 36 00 	vmovapd %xmm1,0x36cf(%rip)        # 4aa0 <a+0x300>
    13d0:	00 
    13d1:	c5 f9 29 05 d7 36 00 	vmovapd %xmm0,0x36d7(%rip)        # 4ab0 <a+0x310>
    13d8:	00 
    13d9:	c5 f9 29 0d 9f 33 00 	vmovapd %xmm1,0x339f(%rip)        # 4780 <b+0x300>
    13e0:	00 
    13e1:	c5 f9 29 05 a7 33 00 	vmovapd %xmm0,0x33a7(%rip)        # 4790 <b+0x310>
    13e8:	00 
    13e9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    13f0:	c5 fd 28 14 02       	vmovapd (%rdx,%rax,1),%ymm2
    13f5:	c5 ed 58 04 01       	vaddpd (%rcx,%rax,1),%ymm2,%ymm0
    13fa:	c5 fd 29 04 06       	vmovapd %ymm0,(%rsi,%rax,1)
    13ff:	48 83 c0 20          	add    $0x20,%rax
    1403:	48 3d 20 03 00 00    	cmp    $0x320,%rax
    1409:	75 e5                	jne    13f0 <main+0x2b0>
    140b:	31 c0                	xor    %eax,%eax
    140d:	0f 1f 00             	nopl   (%rax)
    1410:	c5 fd 28 1c 01       	vmovapd (%rcx,%rax,1),%ymm3
    1415:	c5 e5 58 04 02       	vaddpd (%rdx,%rax,1),%ymm3,%ymm0
    141a:	c5 fd 29 04 06       	vmovapd %ymm0,(%rsi,%rax,1)
    141f:	48 83 c0 20          	add    $0x20,%rax
    1423:	48 3d 20 03 00 00    	cmp    $0x320,%rax
    1429:	75 e5                	jne    1410 <main+0x2d0>
    142b:	48 8d 1d 2e 2d 00 00 	lea    0x2d2e(%rip),%rbx        # 4160 <c>
    1432:	4c 8d b3 20 03 00 00 	lea    0x320(%rbx),%r14
    1439:	4c 8d 25 00 2c 00 00 	lea    0x2c00(%rip),%r12        # 4040 <_ZSt4cout@GLIBCXX_3.4>
    1440:	4c 8d 2d bd 0b 00 00 	lea    0xbbd(%rip),%r13        # 2004 <_IO_stdin_used+0x4>
    1447:	c5 f8 77             	vzeroupper 
    144a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1450:	c5 fb 10 03          	vmovsd (%rbx),%xmm0
    1454:	4c 89 e7             	mov    %r12,%rdi
    1457:	e8 d4 fc ff ff       	call   1130 <_ZNSo9_M_insertIdEERSoT_@plt>
    145c:	48 89 c7             	mov    %rax,%rdi
    145f:	ba 01 00 00 00       	mov    $0x1,%edx
    1464:	4c 89 ee             	mov    %r13,%rsi
    1467:	48 83 c3 08          	add    $0x8,%rbx
    146b:	e8 80 fc ff ff       	call   10f0 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@plt>
    1470:	49 39 de             	cmp    %rbx,%r14
    1473:	75 db                	jne    1450 <main+0x310>
    1475:	48 8b 05 c4 2b 00 00 	mov    0x2bc4(%rip),%rax        # 4040 <_ZSt4cout@GLIBCXX_3.4>
    147c:	48 8b 40 e8          	mov    -0x18(%rax),%rax
    1480:	49 8b 9c 04 f0 00 00 	mov    0xf0(%r12,%rax,1),%rbx
    1487:	00 
    1488:	48 85 db             	test   %rbx,%rbx
    148b:	74 4a                	je     14d7 <main+0x397>
    148d:	80 7b 38 00          	cmpb   $0x0,0x38(%rbx)
    1491:	74 29                	je     14bc <main+0x37c>
    1493:	0f be 73 43          	movsbl 0x43(%rbx),%esi
    1497:	4c 89 e7             	mov    %r12,%rdi
    149a:	e8 21 fc ff ff       	call   10c0 <_ZNSo3putEc@plt>
    149f:	48 89 c7             	mov    %rax,%rdi
    14a2:	e8 29 fc ff ff       	call   10d0 <_ZNSo5flushEv@plt>
    14a7:	48 83 c4 08          	add    $0x8,%rsp
    14ab:	5b                   	pop    %rbx
    14ac:	41 5a                	pop    %r10
    14ae:	41 5c                	pop    %r12
    14b0:	41 5d                	pop    %r13
    14b2:	41 5e                	pop    %r14
    14b4:	31 c0                	xor    %eax,%eax
    14b6:	5d                   	pop    %rbp
    14b7:	49 8d 62 f8          	lea    -0x8(%r10),%rsp
    14bb:	c3                   	ret    
    14bc:	48 89 df             	mov    %rbx,%rdi
    14bf:	e8 3c fc ff ff       	call   1100 <_ZNKSt5ctypeIcE13_M_widen_initEv@plt>
    14c4:	48 8b 03             	mov    (%rbx),%rax
    14c7:	be 0a 00 00 00       	mov    $0xa,%esi
    14cc:	48 89 df             	mov    %rbx,%rdi
    14cf:	ff 50 30             	call   *0x30(%rax)
    14d2:	0f be f0             	movsbl %al,%esi
    14d5:	eb c0                	jmp    1497 <main+0x357>
    14d7:	e8 34 fc ff ff       	call   1110 <_ZSt16__throw_bad_castv@plt>
    14dc:	0f 1f 40 00          	nopl   0x0(%rax)

00000000000014e0 <_GLOBAL__sub_I_a>:
    14e0:	f3 0f 1e fa          	endbr64 
    14e4:	53                   	push   %rbx
    14e5:	48 8d 1d d4 35 00 00 	lea    0x35d4(%rip),%rbx        # 4ac0 <_ZStL8__ioinit>
    14ec:	48 89 df             	mov    %rbx,%rdi
    14ef:	e8 2c fc ff ff       	call   1120 <_ZNSt8ios_base4InitC1Ev@plt>
    14f4:	48 8b 3d fd 2a 00 00 	mov    0x2afd(%rip),%rdi        # 3ff8 <_ZNSt8ios_base4InitD1Ev@GLIBCXX_3.4>
    14fb:	48 89 de             	mov    %rbx,%rsi
    14fe:	48 8d 15 03 2b 00 00 	lea    0x2b03(%rip),%rdx        # 4008 <__dso_handle>
    1505:	5b                   	pop    %rbx
    1506:	e9 d5 fb ff ff       	jmp    10e0 <__cxa_atexit@plt>
    150b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001510 <_start>:
    1510:	f3 0f 1e fa          	endbr64 
    1514:	31 ed                	xor    %ebp,%ebp
    1516:	49 89 d1             	mov    %rdx,%r9
    1519:	5e                   	pop    %rsi
    151a:	48 89 e2             	mov    %rsp,%rdx
    151d:	48 83 e4 f0          	and    $0xfffffffffffffff0,%rsp
    1521:	50                   	push   %rax
    1522:	54                   	push   %rsp
    1523:	45 31 c0             	xor    %r8d,%r8d
    1526:	31 c9                	xor    %ecx,%ecx
    1528:	48 8d 3d 11 fc ff ff 	lea    -0x3ef(%rip),%rdi        # 1140 <main>
    152f:	ff 15 a3 2a 00 00    	call   *0x2aa3(%rip)        # 3fd8 <__libc_start_main@GLIBC_2.34>
    1535:	f4                   	hlt    
    1536:	66 2e 0f 1f 84 00 00 	cs nopw 0x0(%rax,%rax,1)
    153d:	00 00 00 

0000000000001540 <deregister_tm_clones>:
    1540:	48 8d 3d c9 2a 00 00 	lea    0x2ac9(%rip),%rdi        # 4010 <__TMC_END__>
    1547:	48 8d 05 c2 2a 00 00 	lea    0x2ac2(%rip),%rax        # 4010 <__TMC_END__>
    154e:	48 39 f8             	cmp    %rdi,%rax
    1551:	74 15                	je     1568 <deregister_tm_clones+0x28>
    1553:	48 8b 05 86 2a 00 00 	mov    0x2a86(%rip),%rax        # 3fe0 <_ITM_deregisterTMCloneTable@Base>
    155a:	48 85 c0             	test   %rax,%rax
    155d:	74 09                	je     1568 <deregister_tm_clones+0x28>
    155f:	ff e0                	jmp    *%rax
    1561:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    1568:	c3                   	ret    
    1569:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

0000000000001570 <register_tm_clones>:
    1570:	48 8d 3d 99 2a 00 00 	lea    0x2a99(%rip),%rdi        # 4010 <__TMC_END__>
    1577:	48 8d 35 92 2a 00 00 	lea    0x2a92(%rip),%rsi        # 4010 <__TMC_END__>
    157e:	48 29 fe             	sub    %rdi,%rsi
    1581:	48 89 f0             	mov    %rsi,%rax
    1584:	48 c1 ee 3f          	shr    $0x3f,%rsi
    1588:	48 c1 f8 03          	sar    $0x3,%rax
    158c:	48 01 c6             	add    %rax,%rsi
    158f:	48 d1 fe             	sar    %rsi
    1592:	74 14                	je     15a8 <register_tm_clones+0x38>
    1594:	48 8b 05 55 2a 00 00 	mov    0x2a55(%rip),%rax        # 3ff0 <_ITM_registerTMCloneTable@Base>
    159b:	48 85 c0             	test   %rax,%rax
    159e:	74 08                	je     15a8 <register_tm_clones+0x38>
    15a0:	ff e0                	jmp    *%rax
    15a2:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    15a8:	c3                   	ret    
    15a9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

00000000000015b0 <__do_global_dtors_aux>:
    15b0:	f3 0f 1e fa          	endbr64 
    15b4:	80 3d 95 2b 00 00 00 	cmpb   $0x0,0x2b95(%rip)        # 4150 <completed.0>
    15bb:	75 2b                	jne    15e8 <__do_global_dtors_aux+0x38>
    15bd:	55                   	push   %rbp
    15be:	48 83 3d 0a 2a 00 00 	cmpq   $0x0,0x2a0a(%rip)        # 3fd0 <__cxa_finalize@GLIBC_2.2.5>
    15c5:	00 
    15c6:	48 89 e5             	mov    %rsp,%rbp
    15c9:	74 0c                	je     15d7 <__do_global_dtors_aux+0x27>
    15cb:	48 8b 3d 36 2a 00 00 	mov    0x2a36(%rip),%rdi        # 4008 <__dso_handle>
    15d2:	e8 d9 fa ff ff       	call   10b0 <__cxa_finalize@plt>
    15d7:	e8 64 ff ff ff       	call   1540 <deregister_tm_clones>
    15dc:	c6 05 6d 2b 00 00 01 	movb   $0x1,0x2b6d(%rip)        # 4150 <completed.0>
    15e3:	5d                   	pop    %rbp
    15e4:	c3                   	ret    
    15e5:	0f 1f 00             	nopl   (%rax)
    15e8:	c3                   	ret    
    15e9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

00000000000015f0 <frame_dummy>:
    15f0:	f3 0f 1e fa          	endbr64 
    15f4:	e9 77 ff ff ff       	jmp    1570 <register_tm_clones>
    15f9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

0000000000001600 <_Z9add_simd1PdS_S_i>:
    1600:	f3 0f 1e fa          	endbr64 
    1604:	85 c9                	test   %ecx,%ecx
    1606:	7e 22                	jle    162a <_Z9add_simd1PdS_S_i+0x2a>
    1608:	31 c0                	xor    %eax,%eax
    160a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1610:	c5 fd 10 0c c7       	vmovupd (%rdi,%rax,8),%ymm1
    1615:	c5 f5 58 04 c6       	vaddpd (%rsi,%rax,8),%ymm1,%ymm0
    161a:	c5 fd 11 04 c2       	vmovupd %ymm0,(%rdx,%rax,8)
    161f:	48 83 c0 04          	add    $0x4,%rax
    1623:	39 c1                	cmp    %eax,%ecx
    1625:	7f e9                	jg     1610 <_Z9add_simd1PdS_S_i+0x10>
    1627:	c5 f8 77             	vzeroupper 
    162a:	c3                   	ret    
    162b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001630 <_Z9add_simd2PdS_S_i>:
    1630:	f3 0f 1e fa          	endbr64 
    1634:	48 63 c1             	movslq %ecx,%rax
    1637:	85 c0                	test   %eax,%eax
    1639:	0f 8e b7 00 00 00    	jle    16f6 <_Z9add_simd2PdS_S_i+0xc6>
    163f:	83 f8 01             	cmp    $0x1,%eax
    1642:	0f 84 b8 00 00 00    	je     1700 <_Z9add_simd2PdS_S_i+0xd0>
    1648:	4c 8d 47 08          	lea    0x8(%rdi),%r8
    164c:	48 89 d1             	mov    %rdx,%rcx
    164f:	4c 29 c1             	sub    %r8,%rcx
    1652:	48 83 f9 10          	cmp    $0x10,%rcx
    1656:	0f 86 a4 00 00 00    	jbe    1700 <_Z9add_simd2PdS_S_i+0xd0>
    165c:	4c 8d 46 08          	lea    0x8(%rsi),%r8
    1660:	48 89 d1             	mov    %rdx,%rcx
    1663:	4c 29 c1             	sub    %r8,%rcx
    1666:	48 83 f9 10          	cmp    $0x10,%rcx
    166a:	0f 86 90 00 00 00    	jbe    1700 <_Z9add_simd2PdS_S_i+0xd0>
    1670:	8d 48 ff             	lea    -0x1(%rax),%ecx
    1673:	41 89 c1             	mov    %eax,%r9d
    1676:	83 f9 02             	cmp    $0x2,%ecx
    1679:	0f 86 aa 00 00 00    	jbe    1729 <_Z9add_simd2PdS_S_i+0xf9>
    167f:	41 89 c0             	mov    %eax,%r8d
    1682:	41 c1 e8 02          	shr    $0x2,%r8d
    1686:	49 c1 e0 05          	shl    $0x5,%r8
    168a:	31 c9                	xor    %ecx,%ecx
    168c:	0f 1f 40 00          	nopl   0x0(%rax)
    1690:	c5 fd 10 0c 0f       	vmovupd (%rdi,%rcx,1),%ymm1
    1695:	c5 f5 58 04 0e       	vaddpd (%rsi,%rcx,1),%ymm1,%ymm0
    169a:	c5 fd 11 04 0a       	vmovupd %ymm0,(%rdx,%rcx,1)
    169f:	48 83 c1 20          	add    $0x20,%rcx
    16a3:	4c 39 c1             	cmp    %r8,%rcx
    16a6:	75 e8                	jne    1690 <_Z9add_simd2PdS_S_i+0x60>
    16a8:	89 c1                	mov    %eax,%ecx
    16aa:	83 e1 fc             	and    $0xfffffffc,%ecx
    16ad:	41 89 c8             	mov    %ecx,%r8d
    16b0:	39 c8                	cmp    %ecx,%eax
    16b2:	74 3f                	je     16f3 <_Z9add_simd2PdS_S_i+0xc3>
    16b4:	29 c8                	sub    %ecx,%eax
    16b6:	41 89 c1             	mov    %eax,%r9d
    16b9:	83 f8 01             	cmp    $0x1,%eax
    16bc:	74 72                	je     1730 <_Z9add_simd2PdS_S_i+0x100>
    16be:	c5 f8 77             	vzeroupper 
    16c1:	44 89 c0             	mov    %r8d,%eax
    16c4:	c5 f9 10 14 c7       	vmovupd (%rdi,%rax,8),%xmm2
    16c9:	c5 e9 58 04 c6       	vaddpd (%rsi,%rax,8),%xmm2,%xmm0
    16ce:	c5 f9 11 04 c2       	vmovupd %xmm0,(%rdx,%rax,8)
    16d3:	41 f6 c1 01          	test   $0x1,%r9b
    16d7:	74 1d                	je     16f6 <_Z9add_simd2PdS_S_i+0xc6>
    16d9:	41 83 e1 fe          	and    $0xfffffffe,%r9d
    16dd:	44 01 c9             	add    %r9d,%ecx
    16e0:	48 63 c1             	movslq %ecx,%rax
    16e3:	c5 fb 10 04 c7       	vmovsd (%rdi,%rax,8),%xmm0
    16e8:	c5 fb 58 04 c6       	vaddsd (%rsi,%rax,8),%xmm0,%xmm0
    16ed:	c5 fb 11 04 c2       	vmovsd %xmm0,(%rdx,%rax,8)
    16f2:	c3                   	ret    
    16f3:	c5 f8 77             	vzeroupper 
    16f6:	c3                   	ret    
    16f7:	66 0f 1f 84 00 00 00 	nopw   0x0(%rax,%rax,1)
    16fe:	00 00 
    1700:	48 8d 0c c5 00 00 00 	lea    0x0(,%rax,8),%rcx
    1707:	00 
    1708:	31 c0                	xor    %eax,%eax
    170a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1710:	c5 fb 10 04 07       	vmovsd (%rdi,%rax,1),%xmm0
    1715:	c5 fb 58 04 06       	vaddsd (%rsi,%rax,1),%xmm0,%xmm0
    171a:	c5 fb 11 04 02       	vmovsd %xmm0,(%rdx,%rax,1)
    171f:	48 83 c0 08          	add    $0x8,%rax
    1723:	48 39 c1             	cmp    %rax,%rcx
    1726:	75 e8                	jne    1710 <_Z9add_simd2PdS_S_i+0xe0>
    1728:	c3                   	ret    
    1729:	45 31 c0             	xor    %r8d,%r8d
    172c:	31 c9                	xor    %ecx,%ecx
    172e:	eb 91                	jmp    16c1 <_Z9add_simd2PdS_S_i+0x91>
    1730:	c5 f8 77             	vzeroupper 
    1733:	eb ab                	jmp    16e0 <_Z9add_simd2PdS_S_i+0xb0>

Disassembly of section .fini:

0000000000001738 <_fini>:
    1738:	f3 0f 1e fa          	endbr64 
    173c:	48 83 ec 08          	sub    $0x8,%rsp
    1740:	48 83 c4 08          	add    $0x8,%rsp
    1744:	c3                   	ret    
