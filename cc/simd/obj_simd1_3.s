
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
    1020:	ff 35 52 2f 00 00    	push   0x2f52(%rip)        # 3f78 <_GLOBAL_OFFSET_TABLE_+0x8>
    1026:	f2 ff 25 53 2f 00 00 	bnd jmp *0x2f53(%rip)        # 3f80 <_GLOBAL_OFFSET_TABLE_+0x10>
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
    10b0:	f3 0f 1e fa          	endbr64 
    10b4:	68 08 00 00 00       	push   $0x8
    10b9:	f2 e9 61 ff ff ff    	bnd jmp 1020 <_init+0x20>
    10bf:	90                   	nop

Disassembly of section .plt.got:

00000000000010c0 <__cxa_finalize@plt>:
    10c0:	f3 0f 1e fa          	endbr64 
    10c4:	f2 ff 25 05 2f 00 00 	bnd jmp *0x2f05(%rip)        # 3fd0 <__cxa_finalize@GLIBC_2.2.5>
    10cb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

Disassembly of section .plt.sec:

00000000000010d0 <_ZNSo3putEc@plt>:
    10d0:	f3 0f 1e fa          	endbr64 
    10d4:	f2 ff 25 ad 2e 00 00 	bnd jmp *0x2ead(%rip)        # 3f88 <_ZNSo3putEc@GLIBCXX_3.4>
    10db:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

00000000000010e0 <_ZNSo5flushEv@plt>:
    10e0:	f3 0f 1e fa          	endbr64 
    10e4:	f2 ff 25 a5 2e 00 00 	bnd jmp *0x2ea5(%rip)        # 3f90 <_ZNSo5flushEv@GLIBCXX_3.4>
    10eb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

00000000000010f0 <memcpy@plt>:
    10f0:	f3 0f 1e fa          	endbr64 
    10f4:	f2 ff 25 9d 2e 00 00 	bnd jmp *0x2e9d(%rip)        # 3f98 <memcpy@GLIBC_2.14>
    10fb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001100 <__cxa_atexit@plt>:
    1100:	f3 0f 1e fa          	endbr64 
    1104:	f2 ff 25 95 2e 00 00 	bnd jmp *0x2e95(%rip)        # 3fa0 <__cxa_atexit@GLIBC_2.2.5>
    110b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001110 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@plt>:
    1110:	f3 0f 1e fa          	endbr64 
    1114:	f2 ff 25 8d 2e 00 00 	bnd jmp *0x2e8d(%rip)        # 3fa8 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@GLIBCXX_3.4.9>
    111b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001120 <_ZNKSt5ctypeIcE13_M_widen_initEv@plt>:
    1120:	f3 0f 1e fa          	endbr64 
    1124:	f2 ff 25 85 2e 00 00 	bnd jmp *0x2e85(%rip)        # 3fb0 <_ZNKSt5ctypeIcE13_M_widen_initEv@GLIBCXX_3.4.11>
    112b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001130 <_ZSt16__throw_bad_castv@plt>:
    1130:	f3 0f 1e fa          	endbr64 
    1134:	f2 ff 25 7d 2e 00 00 	bnd jmp *0x2e7d(%rip)        # 3fb8 <_ZSt16__throw_bad_castv@GLIBCXX_3.4>
    113b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001140 <_ZNSt8ios_base4InitC1Ev@plt>:
    1140:	f3 0f 1e fa          	endbr64 
    1144:	f2 ff 25 75 2e 00 00 	bnd jmp *0x2e75(%rip)        # 3fc0 <_ZNSt8ios_base4InitC1Ev@GLIBCXX_3.4>
    114b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001150 <_ZNSo9_M_insertIdEERSoT_@plt>:
    1150:	f3 0f 1e fa          	endbr64 
    1154:	f2 ff 25 6d 2e 00 00 	bnd jmp *0x2e6d(%rip)        # 3fc8 <_ZNSo9_M_insertIdEERSoT_@GLIBCXX_3.4.9>
    115b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

Disassembly of section .text:

0000000000001160 <main>:
    1160:	f3 0f 1e fa          	endbr64 
    1164:	4c 8d 54 24 08       	lea    0x8(%rsp),%r10
    1169:	48 83 e4 e0          	and    $0xffffffffffffffe0,%rsp
    116d:	41 ff 72 f8          	push   -0x8(%r10)
    1171:	31 c0                	xor    %eax,%eax
    1173:	48 8d 15 46 39 00 00 	lea    0x3946(%rip),%rdx        # 4ac0 <c>
    117a:	55                   	push   %rbp
    117b:	48 8d 35 7e 3f 00 00 	lea    0x3f7e(%rip),%rsi        # 5100 <a>
    1182:	48 89 e5             	mov    %rsp,%rbp
    1185:	41 56                	push   %r14
    1187:	41 55                	push   %r13
    1189:	41 54                	push   %r12
    118b:	41 52                	push   %r10
    118d:	53                   	push   %rbx
    118e:	48 8d 1d 4b 3c 00 00 	lea    0x3c4b(%rip),%rbx        # 4de0 <b>
    1195:	48 83 ec 08          	sub    $0x8,%rsp
    1199:	c5 fd 28 0d 7f 0e 00 	vmovapd 0xe7f(%rip),%ymm1        # 2020 <_IO_stdin_used+0x20>
    11a0:	00 
    11a1:	c5 fd 28 05 97 0e 00 	vmovapd 0xe97(%rip),%ymm0        # 2040 <_IO_stdin_used+0x40>
    11a8:	00 
    11a9:	c5 fd 29 0d 4f 3f 00 	vmovapd %ymm1,0x3f4f(%rip)        # 5100 <a>
    11b0:	00 
    11b1:	c5 fd 29 05 67 3f 00 	vmovapd %ymm0,0x3f67(%rip)        # 5120 <a+0x20>
    11b8:	00 
    11b9:	c5 fd 29 0d 1f 3c 00 	vmovapd %ymm1,0x3c1f(%rip)        # 4de0 <b>
    11c0:	00 
    11c1:	c5 fd 29 05 37 3c 00 	vmovapd %ymm0,0x3c37(%rip)        # 4e00 <b+0x20>
    11c8:	00 
    11c9:	c5 fd 28 0d 8f 0e 00 	vmovapd 0xe8f(%rip),%ymm1        # 2060 <_IO_stdin_used+0x60>
    11d0:	00 
    11d1:	c5 fd 28 05 a7 0e 00 	vmovapd 0xea7(%rip),%ymm0        # 2080 <_IO_stdin_used+0x80>
    11d8:	00 
    11d9:	c5 fd 29 0d 5f 3f 00 	vmovapd %ymm1,0x3f5f(%rip)        # 5140 <a+0x40>
    11e0:	00 
    11e1:	c5 fd 29 05 77 3f 00 	vmovapd %ymm0,0x3f77(%rip)        # 5160 <a+0x60>
    11e8:	00 
    11e9:	c5 fd 29 0d 2f 3c 00 	vmovapd %ymm1,0x3c2f(%rip)        # 4e20 <b+0x40>
    11f0:	00 
    11f1:	c5 fd 29 05 47 3c 00 	vmovapd %ymm0,0x3c47(%rip)        # 4e40 <b+0x60>
    11f8:	00 
    11f9:	c5 fd 28 0d 9f 0e 00 	vmovapd 0xe9f(%rip),%ymm1        # 20a0 <_IO_stdin_used+0xa0>
    1200:	00 
    1201:	c5 fd 28 05 b7 0e 00 	vmovapd 0xeb7(%rip),%ymm0        # 20c0 <_IO_stdin_used+0xc0>
    1208:	00 
    1209:	c5 fd 29 0d 6f 3f 00 	vmovapd %ymm1,0x3f6f(%rip)        # 5180 <a+0x80>
    1210:	00 
    1211:	c5 fd 29 05 87 3f 00 	vmovapd %ymm0,0x3f87(%rip)        # 51a0 <a+0xa0>
    1218:	00 
    1219:	c5 fd 29 0d 3f 3c 00 	vmovapd %ymm1,0x3c3f(%rip)        # 4e60 <b+0x80>
    1220:	00 
    1221:	c5 fd 29 05 57 3c 00 	vmovapd %ymm0,0x3c57(%rip)        # 4e80 <b+0xa0>
    1228:	00 
    1229:	c5 fd 28 0d af 0e 00 	vmovapd 0xeaf(%rip),%ymm1        # 20e0 <_IO_stdin_used+0xe0>
    1230:	00 
    1231:	c5 fd 28 05 c7 0e 00 	vmovapd 0xec7(%rip),%ymm0        # 2100 <_IO_stdin_used+0x100>
    1238:	00 
    1239:	c5 fd 29 0d 7f 3f 00 	vmovapd %ymm1,0x3f7f(%rip)        # 51c0 <a+0xc0>
    1240:	00 
    1241:	c5 fd 29 05 97 3f 00 	vmovapd %ymm0,0x3f97(%rip)        # 51e0 <a+0xe0>
    1248:	00 
    1249:	c5 fd 29 0d 4f 3c 00 	vmovapd %ymm1,0x3c4f(%rip)        # 4ea0 <b+0xc0>
    1250:	00 
    1251:	c5 fd 29 05 67 3c 00 	vmovapd %ymm0,0x3c67(%rip)        # 4ec0 <b+0xe0>
    1258:	00 
    1259:	c5 fd 28 0d bf 0e 00 	vmovapd 0xebf(%rip),%ymm1        # 2120 <_IO_stdin_used+0x120>
    1260:	00 
    1261:	c5 fd 28 05 d7 0e 00 	vmovapd 0xed7(%rip),%ymm0        # 2140 <_IO_stdin_used+0x140>
    1268:	00 
    1269:	c5 fd 29 0d 8f 3f 00 	vmovapd %ymm1,0x3f8f(%rip)        # 5200 <a+0x100>
    1270:	00 
    1271:	c5 fd 29 0d 67 3c 00 	vmovapd %ymm1,0x3c67(%rip)        # 4ee0 <b+0x100>
    1278:	00 
    1279:	c5 fd 28 0d df 0e 00 	vmovapd 0xedf(%rip),%ymm1        # 2160 <_IO_stdin_used+0x160>
    1280:	00 
    1281:	c5 fd 29 05 97 3f 00 	vmovapd %ymm0,0x3f97(%rip)        # 5220 <a+0x120>
    1288:	00 
    1289:	c5 fd 29 05 6f 3c 00 	vmovapd %ymm0,0x3c6f(%rip)        # 4f00 <b+0x120>
    1290:	00 
    1291:	c5 fd 29 0d a7 3f 00 	vmovapd %ymm1,0x3fa7(%rip)        # 5240 <a+0x140>
    1298:	00 
    1299:	c5 fd 28 05 df 0e 00 	vmovapd 0xedf(%rip),%ymm0        # 2180 <_IO_stdin_used+0x180>
    12a0:	00 
    12a1:	c5 fd 29 0d 77 3c 00 	vmovapd %ymm1,0x3c77(%rip)        # 4f20 <b+0x140>
    12a8:	00 
    12a9:	c5 fd 28 0d ef 0e 00 	vmovapd 0xeef(%rip),%ymm1        # 21a0 <_IO_stdin_used+0x1a0>
    12b0:	00 
    12b1:	c5 fd 29 05 a7 3f 00 	vmovapd %ymm0,0x3fa7(%rip)        # 5260 <a+0x160>
    12b8:	00 
    12b9:	c5 fd 29 05 7f 3c 00 	vmovapd %ymm0,0x3c7f(%rip)        # 4f40 <b+0x160>
    12c0:	00 
    12c1:	c5 fd 29 0d b7 3f 00 	vmovapd %ymm1,0x3fb7(%rip)        # 5280 <a+0x180>
    12c8:	00 
    12c9:	c5 fd 28 05 ef 0e 00 	vmovapd 0xeef(%rip),%ymm0        # 21c0 <_IO_stdin_used+0x1c0>
    12d0:	00 
    12d1:	c5 fd 29 0d 87 3c 00 	vmovapd %ymm1,0x3c87(%rip)        # 4f60 <b+0x180>
    12d8:	00 
    12d9:	c5 fd 28 0d ff 0e 00 	vmovapd 0xeff(%rip),%ymm1        # 21e0 <_IO_stdin_used+0x1e0>
    12e0:	00 
    12e1:	c5 fd 29 05 b7 3f 00 	vmovapd %ymm0,0x3fb7(%rip)        # 52a0 <a+0x1a0>
    12e8:	00 
    12e9:	c5 fd 29 05 8f 3c 00 	vmovapd %ymm0,0x3c8f(%rip)        # 4f80 <b+0x1a0>
    12f0:	00 
    12f1:	c5 fd 29 0d c7 3f 00 	vmovapd %ymm1,0x3fc7(%rip)        # 52c0 <a+0x1c0>
    12f8:	00 
    12f9:	c5 fd 28 05 ff 0e 00 	vmovapd 0xeff(%rip),%ymm0        # 2200 <_IO_stdin_used+0x200>
    1300:	00 
    1301:	c5 fd 29 0d 97 3c 00 	vmovapd %ymm1,0x3c97(%rip)        # 4fa0 <b+0x1c0>
    1308:	00 
    1309:	c5 fd 28 0d 0f 0f 00 	vmovapd 0xf0f(%rip),%ymm1        # 2220 <_IO_stdin_used+0x220>
    1310:	00 
    1311:	c5 fd 29 05 c7 3f 00 	vmovapd %ymm0,0x3fc7(%rip)        # 52e0 <a+0x1e0>
    1318:	00 
    1319:	c5 fd 29 05 9f 3c 00 	vmovapd %ymm0,0x3c9f(%rip)        # 4fc0 <b+0x1e0>
    1320:	00 
    1321:	c5 fd 29 0d d7 3f 00 	vmovapd %ymm1,0x3fd7(%rip)        # 5300 <a+0x200>
    1328:	00 
    1329:	c5 fd 28 05 0f 0f 00 	vmovapd 0xf0f(%rip),%ymm0        # 2240 <_IO_stdin_used+0x240>
    1330:	00 
    1331:	c5 fd 29 0d a7 3c 00 	vmovapd %ymm1,0x3ca7(%rip)        # 4fe0 <b+0x200>
    1338:	00 
    1339:	c5 fd 28 0d 1f 0f 00 	vmovapd 0xf1f(%rip),%ymm1        # 2260 <_IO_stdin_used+0x260>
    1340:	00 
    1341:	c5 fd 29 05 d7 3f 00 	vmovapd %ymm0,0x3fd7(%rip)        # 5320 <a+0x220>
    1348:	00 
    1349:	c5 fd 29 0d ef 3f 00 	vmovapd %ymm1,0x3fef(%rip)        # 5340 <a+0x240>
    1350:	00 
    1351:	c5 fd 29 05 a7 3c 00 	vmovapd %ymm0,0x3ca7(%rip)        # 5000 <b+0x220>
    1358:	00 
    1359:	c5 fd 28 05 1f 0f 00 	vmovapd 0xf1f(%rip),%ymm0        # 2280 <_IO_stdin_used+0x280>
    1360:	00 
    1361:	c5 fd 29 0d b7 3c 00 	vmovapd %ymm1,0x3cb7(%rip)        # 5020 <b+0x240>
    1368:	00 
    1369:	c5 fd 29 05 ef 3f 00 	vmovapd %ymm0,0x3fef(%rip)        # 5360 <a+0x260>
    1370:	00 
    1371:	c5 fd 28 0d 27 0f 00 	vmovapd 0xf27(%rip),%ymm1        # 22a0 <_IO_stdin_used+0x2a0>
    1378:	00 
    1379:	c5 fd 29 05 bf 3c 00 	vmovapd %ymm0,0x3cbf(%rip)        # 5040 <b+0x260>
    1380:	00 
    1381:	c5 fd 28 05 37 0f 00 	vmovapd 0xf37(%rip),%ymm0        # 22c0 <_IO_stdin_used+0x2c0>
    1388:	00 
    1389:	c5 fd 29 0d ef 3f 00 	vmovapd %ymm1,0x3fef(%rip)        # 5380 <a+0x280>
    1390:	00 
    1391:	c5 fd 29 05 07 40 00 	vmovapd %ymm0,0x4007(%rip)        # 53a0 <a+0x2a0>
    1398:	00 
    1399:	c5 fd 29 0d bf 3c 00 	vmovapd %ymm1,0x3cbf(%rip)        # 5060 <b+0x280>
    13a0:	00 
    13a1:	c5 fd 29 05 d7 3c 00 	vmovapd %ymm0,0x3cd7(%rip)        # 5080 <b+0x2a0>
    13a8:	00 
    13a9:	c5 fd 28 0d 2f 0f 00 	vmovapd 0xf2f(%rip),%ymm1        # 22e0 <_IO_stdin_used+0x2e0>
    13b0:	00 
    13b1:	c5 fd 28 05 47 0f 00 	vmovapd 0xf47(%rip),%ymm0        # 2300 <_IO_stdin_used+0x300>
    13b8:	00 
    13b9:	c5 fd 29 0d ff 3f 00 	vmovapd %ymm1,0x3fff(%rip)        # 53c0 <a+0x2c0>
    13c0:	00 
    13c1:	c5 fd 29 05 17 40 00 	vmovapd %ymm0,0x4017(%rip)        # 53e0 <a+0x2e0>
    13c8:	00 
    13c9:	c5 fd 29 0d cf 3c 00 	vmovapd %ymm1,0x3ccf(%rip)        # 50a0 <b+0x2c0>
    13d0:	00 
    13d1:	c5 fd 29 05 e7 3c 00 	vmovapd %ymm0,0x3ce7(%rip)        # 50c0 <b+0x2e0>
    13d8:	00 
    13d9:	c5 f9 28 0d 3f 0f 00 	vmovapd 0xf3f(%rip),%xmm1        # 2320 <_IO_stdin_used+0x320>
    13e0:	00 
    13e1:	c5 f9 28 05 47 0f 00 	vmovapd 0xf47(%rip),%xmm0        # 2330 <_IO_stdin_used+0x330>
    13e8:	00 
    13e9:	c5 f9 29 0d 0f 40 00 	vmovapd %xmm1,0x400f(%rip)        # 5400 <a+0x300>
    13f0:	00 
    13f1:	c5 f9 29 05 17 40 00 	vmovapd %xmm0,0x4017(%rip)        # 5410 <a+0x310>
    13f8:	00 
    13f9:	c5 f9 29 0d df 3c 00 	vmovapd %xmm1,0x3cdf(%rip)        # 50e0 <b+0x300>
    1400:	00 
    1401:	c5 f9 29 05 e7 3c 00 	vmovapd %xmm0,0x3ce7(%rip)        # 50f0 <b+0x310>
    1408:	00 
    1409:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    1410:	c5 fd 28 14 06       	vmovapd (%rsi,%rax,1),%ymm2
    1415:	c5 ed 58 04 03       	vaddpd (%rbx,%rax,1),%ymm2,%ymm0
    141a:	c5 fd 29 04 02       	vmovapd %ymm0,(%rdx,%rax,1)
    141f:	48 83 c0 20          	add    $0x20,%rax
    1423:	48 3d 20 03 00 00    	cmp    $0x320,%rax
    1429:	75 e5                	jne    1410 <main+0x2b0>
    142b:	31 c0                	xor    %eax,%eax
    142d:	0f 1f 00             	nopl   (%rax)
    1430:	c5 fd 28 1c 03       	vmovapd (%rbx,%rax,1),%ymm3
    1435:	c5 e5 58 04 06       	vaddpd (%rsi,%rax,1),%ymm3,%ymm0
    143a:	c5 fd 29 04 02       	vmovapd %ymm0,(%rdx,%rax,1)
    143f:	48 83 c0 20          	add    $0x20,%rax
    1443:	48 3d 20 03 00 00    	cmp    $0x320,%rax
    1449:	75 e5                	jne    1430 <main+0x2d0>
    144b:	ba 20 03 00 00       	mov    $0x320,%edx
    1450:	48 8d 3d 49 33 00 00 	lea    0x3349(%rip),%rdi        # 47a0 <va>
    1457:	c5 f8 77             	vzeroupper 
    145a:	e8 91 fc ff ff       	call   10f0 <memcpy@plt>
    145f:	48 89 de             	mov    %rbx,%rsi
    1462:	ba 20 03 00 00       	mov    $0x320,%edx
    1467:	48 8d 3d 12 30 00 00 	lea    0x3012(%rip),%rdi        # 4480 <vb>
    146e:	e8 7d fc ff ff       	call   10f0 <memcpy@plt>
    1473:	c5 fd 28 1d 05 30 00 	vmovapd 0x3005(%rip),%ymm3        # 4480 <vb>
    147a:	00 
    147b:	c5 fd 28 25 3d 33 00 	vmovapd 0x333d(%rip),%ymm4        # 47c0 <va+0x20>
    1482:	00 
    1483:	c5 e5 58 05 15 33 00 	vaddpd 0x3315(%rip),%ymm3,%ymm0        # 47a0 <va>
    148a:	00 
    148b:	c5 fd 28 2d 4d 33 00 	vmovapd 0x334d(%rip),%ymm5        # 47e0 <va+0x40>
    1492:	00 
    1493:	c5 fd 28 35 65 33 00 	vmovapd 0x3365(%rip),%ymm6        # 4800 <va+0x60>
    149a:	00 
    149b:	c5 fd 29 05 bd 2c 00 	vmovapd %ymm0,0x2cbd(%rip)        # 4160 <vc>
    14a2:	00 
    14a3:	c5 dd 58 05 f5 2f 00 	vaddpd 0x2ff5(%rip),%ymm4,%ymm0        # 44a0 <vb+0x20>
    14aa:	00 
    14ab:	c5 fd 28 3d 6d 33 00 	vmovapd 0x336d(%rip),%ymm7        # 4820 <va+0x80>
    14b2:	00 
    14b3:	c5 fd 28 15 65 30 00 	vmovapd 0x3065(%rip),%ymm2        # 4520 <vb+0xa0>
    14ba:	00 
    14bb:	c5 fd 29 05 bd 2c 00 	vmovapd %ymm0,0x2cbd(%rip)        # 4180 <vc+0x20>
    14c2:	00 
    14c3:	c5 d5 58 05 f5 2f 00 	vaddpd 0x2ff5(%rip),%ymm5,%ymm0        # 44c0 <vb+0x40>
    14ca:	00 
    14cb:	48 8d 1d ee 35 00 00 	lea    0x35ee(%rip),%rbx        # 4ac0 <c>
    14d2:	4c 8d b3 20 03 00 00 	lea    0x320(%rbx),%r14
    14d9:	c5 fd 29 05 bf 2c 00 	vmovapd %ymm0,0x2cbf(%rip)        # 41a0 <vc+0x40>
    14e0:	00 
    14e1:	c5 cd 58 05 f7 2f 00 	vaddpd 0x2ff7(%rip),%ymm6,%ymm0        # 44e0 <vb+0x60>
    14e8:	00 
    14e9:	4c 8d 25 50 2b 00 00 	lea    0x2b50(%rip),%r12        # 4040 <_ZSt4cout@GLIBCXX_3.4>
    14f0:	4c 8d 2d 0d 0b 00 00 	lea    0xb0d(%rip),%r13        # 2004 <_IO_stdin_used+0x4>
    14f7:	c5 fd 29 05 c1 2c 00 	vmovapd %ymm0,0x2cc1(%rip)        # 41c0 <vc+0x60>
    14fe:	00 
    14ff:	c5 c5 58 05 f9 2f 00 	vaddpd 0x2ff9(%rip),%ymm7,%ymm0        # 4500 <vb+0x80>
    1506:	00 
    1507:	c5 fd 29 05 d1 2c 00 	vmovapd %ymm0,0x2cd1(%rip)        # 41e0 <vc+0x80>
    150e:	00 
    150f:	c5 ed 58 05 29 33 00 	vaddpd 0x3329(%rip),%ymm2,%ymm0        # 4840 <va+0xa0>
    1516:	00 
    1517:	c5 fd 29 05 e1 2c 00 	vmovapd %ymm0,0x2ce1(%rip)        # 4200 <vc+0xa0>
    151e:	00 
    151f:	c5 fb 10 05 19 30 00 	vmovsd 0x3019(%rip),%xmm0        # 4540 <vb+0xc0>
    1526:	00 
    1527:	c5 fb 58 05 31 33 00 	vaddsd 0x3331(%rip),%xmm0,%xmm0        # 4860 <va+0xc0>
    152e:	00 
    152f:	c5 fb 11 05 e9 2c 00 	vmovsd %xmm0,0x2ce9(%rip)        # 4220 <vc+0xc0>
    1536:	00 
    1537:	c5 f8 77             	vzeroupper 
    153a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1540:	c5 fb 10 03          	vmovsd (%rbx),%xmm0
    1544:	4c 89 e7             	mov    %r12,%rdi
    1547:	e8 04 fc ff ff       	call   1150 <_ZNSo9_M_insertIdEERSoT_@plt>
    154c:	48 89 c7             	mov    %rax,%rdi
    154f:	ba 01 00 00 00       	mov    $0x1,%edx
    1554:	4c 89 ee             	mov    %r13,%rsi
    1557:	48 83 c3 08          	add    $0x8,%rbx
    155b:	e8 b0 fb ff ff       	call   1110 <_ZSt16__ostream_insertIcSt11char_traitsIcEERSt13basic_ostreamIT_T0_ES6_PKS3_l@plt>
    1560:	4c 39 f3             	cmp    %r14,%rbx
    1563:	75 db                	jne    1540 <main+0x3e0>
    1565:	48 8b 05 d4 2a 00 00 	mov    0x2ad4(%rip),%rax        # 4040 <_ZSt4cout@GLIBCXX_3.4>
    156c:	48 8b 40 e8          	mov    -0x18(%rax),%rax
    1570:	49 8b 9c 04 f0 00 00 	mov    0xf0(%r12,%rax,1),%rbx
    1577:	00 
    1578:	48 85 db             	test   %rbx,%rbx
    157b:	74 4a                	je     15c7 <main+0x467>
    157d:	80 7b 38 00          	cmpb   $0x0,0x38(%rbx)
    1581:	74 29                	je     15ac <main+0x44c>
    1583:	0f be 73 43          	movsbl 0x43(%rbx),%esi
    1587:	4c 89 e7             	mov    %r12,%rdi
    158a:	e8 41 fb ff ff       	call   10d0 <_ZNSo3putEc@plt>
    158f:	48 89 c7             	mov    %rax,%rdi
    1592:	e8 49 fb ff ff       	call   10e0 <_ZNSo5flushEv@plt>
    1597:	48 83 c4 08          	add    $0x8,%rsp
    159b:	5b                   	pop    %rbx
    159c:	41 5a                	pop    %r10
    159e:	41 5c                	pop    %r12
    15a0:	41 5d                	pop    %r13
    15a2:	41 5e                	pop    %r14
    15a4:	31 c0                	xor    %eax,%eax
    15a6:	5d                   	pop    %rbp
    15a7:	49 8d 62 f8          	lea    -0x8(%r10),%rsp
    15ab:	c3                   	ret    
    15ac:	48 89 df             	mov    %rbx,%rdi
    15af:	e8 6c fb ff ff       	call   1120 <_ZNKSt5ctypeIcE13_M_widen_initEv@plt>
    15b4:	48 8b 03             	mov    (%rbx),%rax
    15b7:	be 0a 00 00 00       	mov    $0xa,%esi
    15bc:	48 89 df             	mov    %rbx,%rdi
    15bf:	ff 50 30             	call   *0x30(%rax)
    15c2:	0f be f0             	movsbl %al,%esi
    15c5:	eb c0                	jmp    1587 <main+0x427>
    15c7:	e8 64 fb ff ff       	call   1130 <_ZSt16__throw_bad_castv@plt>
    15cc:	0f 1f 40 00          	nopl   0x0(%rax)

00000000000015d0 <_GLOBAL__sub_I_a>:
    15d0:	f3 0f 1e fa          	endbr64 
    15d4:	53                   	push   %rbx
    15d5:	48 8d 1d 44 3e 00 00 	lea    0x3e44(%rip),%rbx        # 5420 <_ZStL8__ioinit>
    15dc:	48 89 df             	mov    %rbx,%rdi
    15df:	e8 5c fb ff ff       	call   1140 <_ZNSt8ios_base4InitC1Ev@plt>
    15e4:	48 8b 3d 0d 2a 00 00 	mov    0x2a0d(%rip),%rdi        # 3ff8 <_ZNSt8ios_base4InitD1Ev@GLIBCXX_3.4>
    15eb:	48 89 de             	mov    %rbx,%rsi
    15ee:	48 8d 15 13 2a 00 00 	lea    0x2a13(%rip),%rdx        # 4008 <__dso_handle>
    15f5:	5b                   	pop    %rbx
    15f6:	e9 05 fb ff ff       	jmp    1100 <__cxa_atexit@plt>
    15fb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001600 <_start>:
    1600:	f3 0f 1e fa          	endbr64 
    1604:	31 ed                	xor    %ebp,%ebp
    1606:	49 89 d1             	mov    %rdx,%r9
    1609:	5e                   	pop    %rsi
    160a:	48 89 e2             	mov    %rsp,%rdx
    160d:	48 83 e4 f0          	and    $0xfffffffffffffff0,%rsp
    1611:	50                   	push   %rax
    1612:	54                   	push   %rsp
    1613:	45 31 c0             	xor    %r8d,%r8d
    1616:	31 c9                	xor    %ecx,%ecx
    1618:	48 8d 3d 41 fb ff ff 	lea    -0x4bf(%rip),%rdi        # 1160 <main>
    161f:	ff 15 b3 29 00 00    	call   *0x29b3(%rip)        # 3fd8 <__libc_start_main@GLIBC_2.34>
    1625:	f4                   	hlt    
    1626:	66 2e 0f 1f 84 00 00 	cs nopw 0x0(%rax,%rax,1)
    162d:	00 00 00 

0000000000001630 <deregister_tm_clones>:
    1630:	48 8d 3d d9 29 00 00 	lea    0x29d9(%rip),%rdi        # 4010 <__TMC_END__>
    1637:	48 8d 05 d2 29 00 00 	lea    0x29d2(%rip),%rax        # 4010 <__TMC_END__>
    163e:	48 39 f8             	cmp    %rdi,%rax
    1641:	74 15                	je     1658 <deregister_tm_clones+0x28>
    1643:	48 8b 05 96 29 00 00 	mov    0x2996(%rip),%rax        # 3fe0 <_ITM_deregisterTMCloneTable@Base>
    164a:	48 85 c0             	test   %rax,%rax
    164d:	74 09                	je     1658 <deregister_tm_clones+0x28>
    164f:	ff e0                	jmp    *%rax
    1651:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)
    1658:	c3                   	ret    
    1659:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

0000000000001660 <register_tm_clones>:
    1660:	48 8d 3d a9 29 00 00 	lea    0x29a9(%rip),%rdi        # 4010 <__TMC_END__>
    1667:	48 8d 35 a2 29 00 00 	lea    0x29a2(%rip),%rsi        # 4010 <__TMC_END__>
    166e:	48 29 fe             	sub    %rdi,%rsi
    1671:	48 89 f0             	mov    %rsi,%rax
    1674:	48 c1 ee 3f          	shr    $0x3f,%rsi
    1678:	48 c1 f8 03          	sar    $0x3,%rax
    167c:	48 01 c6             	add    %rax,%rsi
    167f:	48 d1 fe             	sar    %rsi
    1682:	74 14                	je     1698 <register_tm_clones+0x38>
    1684:	48 8b 05 65 29 00 00 	mov    0x2965(%rip),%rax        # 3ff0 <_ITM_registerTMCloneTable@Base>
    168b:	48 85 c0             	test   %rax,%rax
    168e:	74 08                	je     1698 <register_tm_clones+0x38>
    1690:	ff e0                	jmp    *%rax
    1692:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1698:	c3                   	ret    
    1699:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

00000000000016a0 <__do_global_dtors_aux>:
    16a0:	f3 0f 1e fa          	endbr64 
    16a4:	80 3d a5 2a 00 00 00 	cmpb   $0x0,0x2aa5(%rip)        # 4150 <completed.0>
    16ab:	75 2b                	jne    16d8 <__do_global_dtors_aux+0x38>
    16ad:	55                   	push   %rbp
    16ae:	48 83 3d 1a 29 00 00 	cmpq   $0x0,0x291a(%rip)        # 3fd0 <__cxa_finalize@GLIBC_2.2.5>
    16b5:	00 
    16b6:	48 89 e5             	mov    %rsp,%rbp
    16b9:	74 0c                	je     16c7 <__do_global_dtors_aux+0x27>
    16bb:	48 8b 3d 46 29 00 00 	mov    0x2946(%rip),%rdi        # 4008 <__dso_handle>
    16c2:	e8 f9 f9 ff ff       	call   10c0 <__cxa_finalize@plt>
    16c7:	e8 64 ff ff ff       	call   1630 <deregister_tm_clones>
    16cc:	c6 05 7d 2a 00 00 01 	movb   $0x1,0x2a7d(%rip)        # 4150 <completed.0>
    16d3:	5d                   	pop    %rbp
    16d4:	c3                   	ret    
    16d5:	0f 1f 00             	nopl   (%rax)
    16d8:	c3                   	ret    
    16d9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

00000000000016e0 <frame_dummy>:
    16e0:	f3 0f 1e fa          	endbr64 
    16e4:	e9 77 ff ff ff       	jmp    1660 <register_tm_clones>
    16e9:	0f 1f 80 00 00 00 00 	nopl   0x0(%rax)

00000000000016f0 <_Z9add_simd0PdS_S_i>:
    16f0:	f3 0f 1e fa          	endbr64 
    16f4:	48 63 c1             	movslq %ecx,%rax
    16f7:	85 c0                	test   %eax,%eax
    16f9:	0f 8e b7 00 00 00    	jle    17b6 <_Z9add_simd0PdS_S_i+0xc6>
    16ff:	83 f8 01             	cmp    $0x1,%eax
    1702:	0f 84 b8 00 00 00    	je     17c0 <_Z9add_simd0PdS_S_i+0xd0>
    1708:	4c 8d 47 08          	lea    0x8(%rdi),%r8
    170c:	48 89 d1             	mov    %rdx,%rcx
    170f:	4c 29 c1             	sub    %r8,%rcx
    1712:	48 83 f9 10          	cmp    $0x10,%rcx
    1716:	0f 86 a4 00 00 00    	jbe    17c0 <_Z9add_simd0PdS_S_i+0xd0>
    171c:	4c 8d 46 08          	lea    0x8(%rsi),%r8
    1720:	48 89 d1             	mov    %rdx,%rcx
    1723:	4c 29 c1             	sub    %r8,%rcx
    1726:	48 83 f9 10          	cmp    $0x10,%rcx
    172a:	0f 86 90 00 00 00    	jbe    17c0 <_Z9add_simd0PdS_S_i+0xd0>
    1730:	8d 48 ff             	lea    -0x1(%rax),%ecx
    1733:	41 89 c1             	mov    %eax,%r9d
    1736:	83 f9 02             	cmp    $0x2,%ecx
    1739:	0f 86 aa 00 00 00    	jbe    17e9 <_Z9add_simd0PdS_S_i+0xf9>
    173f:	41 89 c0             	mov    %eax,%r8d
    1742:	41 c1 e8 02          	shr    $0x2,%r8d
    1746:	49 c1 e0 05          	shl    $0x5,%r8
    174a:	31 c9                	xor    %ecx,%ecx
    174c:	0f 1f 40 00          	nopl   0x0(%rax)
    1750:	c5 fd 10 0c 0f       	vmovupd (%rdi,%rcx,1),%ymm1
    1755:	c5 f5 58 04 0e       	vaddpd (%rsi,%rcx,1),%ymm1,%ymm0
    175a:	c5 fd 11 04 0a       	vmovupd %ymm0,(%rdx,%rcx,1)
    175f:	48 83 c1 20          	add    $0x20,%rcx
    1763:	4c 39 c1             	cmp    %r8,%rcx
    1766:	75 e8                	jne    1750 <_Z9add_simd0PdS_S_i+0x60>
    1768:	89 c1                	mov    %eax,%ecx
    176a:	83 e1 fc             	and    $0xfffffffc,%ecx
    176d:	41 89 c8             	mov    %ecx,%r8d
    1770:	39 c8                	cmp    %ecx,%eax
    1772:	74 3f                	je     17b3 <_Z9add_simd0PdS_S_i+0xc3>
    1774:	29 c8                	sub    %ecx,%eax
    1776:	41 89 c1             	mov    %eax,%r9d
    1779:	83 f8 01             	cmp    $0x1,%eax
    177c:	74 72                	je     17f0 <_Z9add_simd0PdS_S_i+0x100>
    177e:	c5 f8 77             	vzeroupper 
    1781:	44 89 c0             	mov    %r8d,%eax
    1784:	c5 f9 10 14 c7       	vmovupd (%rdi,%rax,8),%xmm2
    1789:	c5 e9 58 04 c6       	vaddpd (%rsi,%rax,8),%xmm2,%xmm0
    178e:	c5 f9 11 04 c2       	vmovupd %xmm0,(%rdx,%rax,8)
    1793:	41 f6 c1 01          	test   $0x1,%r9b
    1797:	74 1d                	je     17b6 <_Z9add_simd0PdS_S_i+0xc6>
    1799:	41 83 e1 fe          	and    $0xfffffffe,%r9d
    179d:	44 01 c9             	add    %r9d,%ecx
    17a0:	48 63 c1             	movslq %ecx,%rax
    17a3:	c5 fb 10 04 c7       	vmovsd (%rdi,%rax,8),%xmm0
    17a8:	c5 fb 58 04 c6       	vaddsd (%rsi,%rax,8),%xmm0,%xmm0
    17ad:	c5 fb 11 04 c2       	vmovsd %xmm0,(%rdx,%rax,8)
    17b2:	c3                   	ret    
    17b3:	c5 f8 77             	vzeroupper 
    17b6:	c3                   	ret    
    17b7:	66 0f 1f 84 00 00 00 	nopw   0x0(%rax,%rax,1)
    17be:	00 00 
    17c0:	48 8d 0c c5 00 00 00 	lea    0x0(,%rax,8),%rcx
    17c7:	00 
    17c8:	31 c0                	xor    %eax,%eax
    17ca:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    17d0:	c5 fb 10 04 07       	vmovsd (%rdi,%rax,1),%xmm0
    17d5:	c5 fb 58 04 06       	vaddsd (%rsi,%rax,1),%xmm0,%xmm0
    17da:	c5 fb 11 04 02       	vmovsd %xmm0,(%rdx,%rax,1)
    17df:	48 83 c0 08          	add    $0x8,%rax
    17e3:	48 39 c1             	cmp    %rax,%rcx
    17e6:	75 e8                	jne    17d0 <_Z9add_simd0PdS_S_i+0xe0>
    17e8:	c3                   	ret    
    17e9:	45 31 c0             	xor    %r8d,%r8d
    17ec:	31 c9                	xor    %ecx,%ecx
    17ee:	eb 91                	jmp    1781 <_Z9add_simd0PdS_S_i+0x91>
    17f0:	c5 f8 77             	vzeroupper 
    17f3:	eb ab                	jmp    17a0 <_Z9add_simd0PdS_S_i+0xb0>
    17f5:	66 66 2e 0f 1f 84 00 	data16 cs nopw 0x0(%rax,%rax,1)
    17fc:	00 00 00 00 

0000000000001800 <_Z9add_simd1PdS_S_i>:
    1800:	f3 0f 1e fa          	endbr64 
    1804:	85 c9                	test   %ecx,%ecx
    1806:	7e 22                	jle    182a <_Z9add_simd1PdS_S_i+0x2a>
    1808:	31 c0                	xor    %eax,%eax
    180a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1810:	c5 fd 10 0c c7       	vmovupd (%rdi,%rax,8),%ymm1
    1815:	c5 f5 58 04 c6       	vaddpd (%rsi,%rax,8),%ymm1,%ymm0
    181a:	c5 fd 11 04 c2       	vmovupd %ymm0,(%rdx,%rax,8)
    181f:	48 83 c0 04          	add    $0x4,%rax
    1823:	39 c1                	cmp    %eax,%ecx
    1825:	7f e9                	jg     1810 <_Z9add_simd1PdS_S_i+0x10>
    1827:	c5 f8 77             	vzeroupper 
    182a:	c3                   	ret    
    182b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)

0000000000001830 <_Z9add_simd2PdS_S_i>:
    1830:	f3 0f 1e fa          	endbr64 
    1834:	48 63 c1             	movslq %ecx,%rax
    1837:	85 c0                	test   %eax,%eax
    1839:	0f 8e b7 00 00 00    	jle    18f6 <_Z9add_simd2PdS_S_i+0xc6>
    183f:	83 f8 01             	cmp    $0x1,%eax
    1842:	0f 84 b8 00 00 00    	je     1900 <_Z9add_simd2PdS_S_i+0xd0>
    1848:	4c 8d 47 08          	lea    0x8(%rdi),%r8
    184c:	48 89 d1             	mov    %rdx,%rcx
    184f:	4c 29 c1             	sub    %r8,%rcx
    1852:	48 83 f9 10          	cmp    $0x10,%rcx
    1856:	0f 86 a4 00 00 00    	jbe    1900 <_Z9add_simd2PdS_S_i+0xd0>
    185c:	4c 8d 46 08          	lea    0x8(%rsi),%r8
    1860:	48 89 d1             	mov    %rdx,%rcx
    1863:	4c 29 c1             	sub    %r8,%rcx
    1866:	48 83 f9 10          	cmp    $0x10,%rcx
    186a:	0f 86 90 00 00 00    	jbe    1900 <_Z9add_simd2PdS_S_i+0xd0>
    1870:	8d 48 ff             	lea    -0x1(%rax),%ecx
    1873:	41 89 c1             	mov    %eax,%r9d
    1876:	83 f9 02             	cmp    $0x2,%ecx
    1879:	0f 86 aa 00 00 00    	jbe    1929 <_Z9add_simd2PdS_S_i+0xf9>
    187f:	41 89 c0             	mov    %eax,%r8d
    1882:	41 c1 e8 02          	shr    $0x2,%r8d
    1886:	49 c1 e0 05          	shl    $0x5,%r8
    188a:	31 c9                	xor    %ecx,%ecx
    188c:	0f 1f 40 00          	nopl   0x0(%rax)
    1890:	c5 fd 10 0c 0f       	vmovupd (%rdi,%rcx,1),%ymm1
    1895:	c5 f5 58 04 0e       	vaddpd (%rsi,%rcx,1),%ymm1,%ymm0
    189a:	c5 fd 11 04 0a       	vmovupd %ymm0,(%rdx,%rcx,1)
    189f:	48 83 c1 20          	add    $0x20,%rcx
    18a3:	4c 39 c1             	cmp    %r8,%rcx
    18a6:	75 e8                	jne    1890 <_Z9add_simd2PdS_S_i+0x60>
    18a8:	89 c1                	mov    %eax,%ecx
    18aa:	83 e1 fc             	and    $0xfffffffc,%ecx
    18ad:	41 89 c8             	mov    %ecx,%r8d
    18b0:	39 c8                	cmp    %ecx,%eax
    18b2:	74 3f                	je     18f3 <_Z9add_simd2PdS_S_i+0xc3>
    18b4:	29 c8                	sub    %ecx,%eax
    18b6:	41 89 c1             	mov    %eax,%r9d
    18b9:	83 f8 01             	cmp    $0x1,%eax
    18bc:	74 72                	je     1930 <_Z9add_simd2PdS_S_i+0x100>
    18be:	c5 f8 77             	vzeroupper 
    18c1:	44 89 c0             	mov    %r8d,%eax
    18c4:	c5 f9 10 14 c7       	vmovupd (%rdi,%rax,8),%xmm2
    18c9:	c5 e9 58 04 c6       	vaddpd (%rsi,%rax,8),%xmm2,%xmm0
    18ce:	c5 f9 11 04 c2       	vmovupd %xmm0,(%rdx,%rax,8)
    18d3:	41 f6 c1 01          	test   $0x1,%r9b
    18d7:	74 1d                	je     18f6 <_Z9add_simd2PdS_S_i+0xc6>
    18d9:	41 83 e1 fe          	and    $0xfffffffe,%r9d
    18dd:	44 01 c9             	add    %r9d,%ecx
    18e0:	48 63 c1             	movslq %ecx,%rax
    18e3:	c5 fb 10 04 c7       	vmovsd (%rdi,%rax,8),%xmm0
    18e8:	c5 fb 58 04 c6       	vaddsd (%rsi,%rax,8),%xmm0,%xmm0
    18ed:	c5 fb 11 04 c2       	vmovsd %xmm0,(%rdx,%rax,8)
    18f2:	c3                   	ret    
    18f3:	c5 f8 77             	vzeroupper 
    18f6:	c3                   	ret    
    18f7:	66 0f 1f 84 00 00 00 	nopw   0x0(%rax,%rax,1)
    18fe:	00 00 
    1900:	48 8d 0c c5 00 00 00 	lea    0x0(,%rax,8),%rcx
    1907:	00 
    1908:	31 c0                	xor    %eax,%eax
    190a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
    1910:	c5 fb 10 04 07       	vmovsd (%rdi,%rax,1),%xmm0
    1915:	c5 fb 58 04 06       	vaddsd (%rsi,%rax,1),%xmm0,%xmm0
    191a:	c5 fb 11 04 02       	vmovsd %xmm0,(%rdx,%rax,1)
    191f:	48 83 c0 08          	add    $0x8,%rax
    1923:	48 39 c1             	cmp    %rax,%rcx
    1926:	75 e8                	jne    1910 <_Z9add_simd2PdS_S_i+0xe0>
    1928:	c3                   	ret    
    1929:	45 31 c0             	xor    %r8d,%r8d
    192c:	31 c9                	xor    %ecx,%ecx
    192e:	eb 91                	jmp    18c1 <_Z9add_simd2PdS_S_i+0x91>
    1930:	c5 f8 77             	vzeroupper 
    1933:	eb ab                	jmp    18e0 <_Z9add_simd2PdS_S_i+0xb0>

Disassembly of section .fini:

0000000000001938 <_fini>:
    1938:	f3 0f 1e fa          	endbr64 
    193c:	48 83 ec 08          	sub    $0x8,%rsp
    1940:	48 83 c4 08          	add    $0x8,%rsp
    1944:	c3                   	ret    
