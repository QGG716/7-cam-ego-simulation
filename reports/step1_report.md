# Step 1 — SIM-V0.2-vfov130

## 结果
**本轮已完成。** 已在现有GPU服务器Isaac Sim 6.0.1.0中加载原设备USD并真实渲染7路原生分辨率ideal图像、7张有效区域掩膜、逐图元数据、1张标明相机位置/方向的worn外部总览和C0/C1/C3角度靶标。

22/22个实际角度检查通过，可见靶标最大像素残差 **0.271323 px**。10项离线测试通过，和真实渲染分开记录。

## 已完成内容
- 安全解压并核对25个原包文件，阅读指定资料、客户PDF、组成图和4页图纸。原始ZIP、PDF、图纸、模型和代码未改写。
- 从原layout_parameters.json继承活动配置；仅落实前向三目VFOV130°，C0独立fx/fy。来源分层见parameter_changes.md。
- 复用rig_common.py坐标/布局/射线逻辑，在工作副本修正camera_specs()；未重做STEP、DXF或PDF。
- 以相对引用和USD覆盖层保留全部原设备及佩戴代理结构，无移动光心、缩小结构或重复0.001缩放。
- 世界高度1.6 m独立于内部外参；近裁剪0.0001 m。新增本地照明、地面/顶部棋盘、侧面色块及前向非对称标志，无外部场景下载。
- 保留ideal/body/worn开关。本轮仅ideal七路成像与worn外部总览。总览标注在渲染后叠加，不进入传感器图像。
- 本地提供PowerShell运行入口，实际图像、日志、场景与数据均已回传。

## 实际执行命令
| 命令/动作 | 结果 |
| --- | --- |
| zipfile路径、大小、符号链接检查/解压/SHA-256核对 | 25文件完整，baseline_manifest.json |
| .venv/Scripts/python.exe scripts/build_step1.py | 7相机派生标定与USD覆盖层成功 |
| .venv/Scripts/python.exe tests/test_offline.py | 10 tests，0 failures，0 errors |
| Paramiko SSH/SFTP至专用远端工程目录 | 必要文件上传、结果回传成功 |
| 远端Isaac Python运行scripts/start_remote_job.py --task all | 最终完整运行PASS，isaac_all.log |
| .venv/Scripts/python.exe scripts/finalize_step1.py | 尺寸/掩膜/时间/配置/总览/角度产物核验PASS |
| powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_step1.ps1 | 实际运行成功，派生+离线测试PASS |

ZIP SHA-256：074543a3f2958ef8c7470449de6174e67edb883939fbf5df137e773084a5c75d。
活动配置SHA-256：dfe120ea02244399386dbef1386900813e06f9f5ab87409868eeeddb50bff44d。派生标定、USD和元数据均记录此值。

## 七路最终参数
| ID | 位置B，mm | 光轴 / 图像上方B | 尺寸 | 名义FPS | 投影/视场 | fx / fy，px | 主点，px |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 0,0,0 | +X / +Z | 1920×1080 | 30 | 针孔H120°/V130° | 554.256258 / 251.806135 | 960,540 |
| C1 | 0,31.5,0 | +X / +Z | 1600×1300 | 30 | 等距H160°/V130° | 572.957795 / 572.957795 | 800,650 |
| C2 | 0,-31.5,0 | +X / +Z | 1600×1300 | 30 | 等距H160°/V130° | 572.957795 / 572.957795 | 800,650 |
| C3 | -16,55,20 | +Z / -X | 1080×960 | 30 | 等距圆形成像220° | 250.017947 / 250.017947 | 540,480 |
| C4 | -16,55,-20 | -Z / +X | 1080×960 | 30 | 等距圆形成像220° | 250.017947 / 250.017947 | 540,480 |
| C5 | -16,-55,20 | +Z / -X | 1080×960 | 30 | 等距圆形成像220° | 250.017947 / 250.017947 | 540,480 |
| C6 | -16,-55,-20 | -Z / +X | 1080×960 | 30 | 等距圆形成像220° | 250.017947 / 250.017947 | 540,480 |

C1/C2为半径800 px圆与画幅交集；C3–C6有效圆直径960 px、最大离轴110°。I0位于(-18,0,0) mm，轴与B平行，名义200 Hz，仅安装配置不采样。所有结构及标定均为名义仿真基线，不是厂家实测。

## 验证状态
| 验证 | 状态 | 证据 |
| --- | --- | --- |
| 原包不变、配置继承 | PASS，离线 | baseline_manifest.json、tests/test_offline.py |
| ID/位置/轴向、63/110/40 mm关系 | PASS，离线 | offline_results.json |
| 正交性/行列式/四元数/双向外参/单位 | PASS，离线 | 同上 |
| 派生视场/有效圆/像素射线往返/配置一致 | PASS，离线 | 同上 |
| Isaac加载、相机属性/schema/光心/朝向/近裁剪 | PASS，实际运行 | usd_runtime_verification.json、isaac_all.log |
| ideal七路静态成像及掩膜 | PASS，真实渲染 | outputs/step1/ideal/ |
| worn外部总览 | PASS，真实渲染+后处理标注 | worn_overview_raw.png / worn_overview.png |
| 角度检查 | PASS，真实检测22/22 | angle_results.json/csv、angles/ |

离线结果是本轮新执行的10个用例（含多项断言），没有沿用原包“90项通过”。像素中心为(col+0.5,row+0.5)，连续边界[0,W]×[0,H]，主点(W/2,H/2)。

角度检查：C0水平±59°内/±61°外，垂直±64°内/±66°外，8/8；C1水平±79°内/±81°外，垂直±64°内/±66°外，8/8；C3的0°/60°/95°/105°可见，115°不可见，加135°方位角的105°目标可见，6/6。

每次仅显示一个半径6 mm、距离1 m的自发光球，角半径约0.344°，不跨最近1°边界。角度场景隐藏全部设备/佩戴结构，无地板或其他目标遮挡。整图检测使用RGB亮度阈值80、至少2像素连通区域、亮度加权质心；检测器不接收理论位置。可见性必须匹配且残差≤2 px，这是本轮软件检查阈值，不是新增客户验收指标。原始渲染和有效区域处理后的全尺寸图均保留。

## 投影实现和限制
C0原生OmniLensDistortionOpenCvPinholeAPI，显式fx/fy、零畸变、1920×1080 imageSize。实测±64°靶标在画幅内，排除了仅修改配置字段或拉伸旧窄视场图像的情况。

C1–C6使用原包RTX fisheyePolynomial，并从活动配置重新派生全部ftheta属性：θ=r/f，A=C=D=E=0，B=1/f。C3实测95°/105°可见，确认未退化为普通针孔或180°镜头。没有重采样或跨相机图像融合。

legacy鱼眼属性在当前版本已弃用，日志有警告；本轮仅确认Isaac 6.0.1.0和当前驱动，不承诺其他版本。[NVIDIA 6.0文档](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_camera.html)说明LUT和schema相关限制，本轮避免混用。安装源码证据见环境报告。

七路来自同一静态场景、固定姿态；timeline暂停，逐路时间断言为0秒，按路顺序渲染。名义30 FPS只保留配置，未验证七路并行帧率、硬件同步、IMU或SLAM。黑色有效圆外区域由独立掩膜表示，不是结构遮挡。图像内容可用于投影检查，不代表真实镜头清晰度、ISP或曝光性能验收。

## 修复记录与未完成项
当前Step 1范围内无阻断项。保留初始许可环境变量错误、C3小靶标漏检和总览环境父节点缺少Xform的失败记录；均作最小修复后实际重跑，未更改视场或设备布局。详见environment.md和诊断日志。

三模式遮挡率/覆盖率、运动、IMU动态采样、连续轨迹、全景融合、深度算法、SLAM/VIO、布局优化和长时性能均未实施；本轮停止，不进入第二阶段。

## 打开哪些文件
1. outputs/step1/seven_camera_preview.png；ideal/C0.png至C6.png为原生图。
2. outputs/step1/worn_overview.png；raw版本是不带标注的原始渲染。
3. outputs/step1/angle_checks_preview.png和angle_results.csv；angles/保留全图。
4. Isaac打开scenes/inspection_scene.usda；外部视角打开scenes/worn_overview.usda并选择/World/OverviewCamera。请保持相对目录布局。

复现命令见README；scripts/run_step1.ps1 -Render包括上传、渲染、回传与核验。

## 变更与Git
新增活动配置/派生标定、src工作代码、USD覆盖层/检查场景、离线测试、运行/回传/核验脚本、实际输出和报告；更新README和环境路径配置。原assets/baseline与ZIP保持不变；初始缺包报告归档于reports/preflight_initial。

Step 1完成时尚未初始化Git；后续用户明确授权发布到 https://github.com/QGG716/7-cam-ego-simulation ，本次提交保留该仓库已有main历史。客户原始资料、本机连接配置和SSH文件不纳入公开提交。此前GPU服务器上传已获授权；其他工程及服务器环境未修改。
