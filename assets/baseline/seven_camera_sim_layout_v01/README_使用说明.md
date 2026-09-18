# 七目相机与IMU仿真结构布置包｜SIM-V0.1

**用途：**在Isaac中建立一个确定、可复现的相机/IMU布局，开展视场、遮挡和后续视觉惯性算法试验。

**性质：**这是根据客户PDF与设备组成图提出的一版名义仿真布局，不是通过图像反求得到的实物CAD，不是制造图纸，也不是出厂标定文件。没有给客户需求新增尺寸公差、器件型号或算法性能承诺。原客户PDF和此前研制方案均未修改。

## 1. 先看什么

- `drawings/七目相机IMU_仿真结构布局_SIM-V0.1.pdf`：4张A3图纸，包含三视图、光心位置、外参定义、佩戴占位及交接说明。
- `models/inspection_scene.usda`：打开即有本体、佩戴占位、灯光、地面和一个前方目标，用于检查模型。它不是SLAM基准场景。
- `config/nominal_extrinsics.json`：所有相机/IMU的名义位置、旋转矩阵、四元数、双向4×4外参和投影假设。

## 2. 来源与假设不能混淆

| 类别 | 已知内容 | 本包的处理 |
|---|---|---|
| D：客户PDF第2页§3 | 三颗相机水平排列；左右中心距63 mm；中间位于中点 | 保留63 mm与中点关系；在仿真中将中心解释为名义光学投影中心 |
| D：客户PDF第2页§3 | 主相机1920×1080下限、双副1600×1300下限、四目1080×960下限 | 各路采用对应最低分辨率作为本次名义配置 |
| D：客户PDF第2页§3 | 中间HFOV120 deg，左右HFOV160 deg；四目需要说明D/H/V FOV与有效区域 | 前向HFOV保留；真实投影模型和有效区域未给出，单独设置仿真假设 |
| D：客户PDF第6页§9 | IMU原始六轴，输出频率至少200 Hz；需要坐标与外参 | 定义IMU安装坐标；配置默认200 Hz，但本包未实现IMU采样 |
| S：组成图 | 前三目、左右上下四目、两个主控、SYNC；四目标220°，IMU标IMUx1000 | 保留图的信息，不提升为PDF硬指标 |
| A：本版设计 | 环视横向间距110 mm、上下40 mm、后移16 mm、IMU后移18 mm | 用作可修改的基线，不声称来自测量 |
| A：本版设计 | 光轴方向、图像滚转角、外壳/镜筒/散热块/头带/线束/头部尺寸 | 用于遮挡占位和空间变换，不是厂家结构参数 |

原始组成图右副相机写1630×1300，PDF是两路副相机“不低于1600×1300”。本包两路采用1600×1300，不将图中的1630解释为已经确认的规格。“IMUx1000”的单位、内部采样/对外输出口径未确认；1000 Hz不替代客户PDF的200 Hz下限。

原始PDF和组成图的副本位于`sources/`，只是方便仿真开发查阅。来源原文优先，图纸中的A项不能反向解释为客户条款。

## 3. 坐标系与完整位置

B为右手系：原点在C0主相机的名义光学投影中心，+X朝设备正前方，+Y朝佩戴者左侧，+Z向上。左右始终按佩戴者，不按面对设备的观察者命名。

| ID | 传感器 | x,y,z（mm） | 光轴（B） | 图像上方（B） |
|---|---|---|---|---|
| C0 | 前向主相机 | 0,0,0 | +X | +Z |
| C1 | 前向左副相机 | 0,+31.5,0 | +X | +Z |
| C2 | 前向右副相机 | 0,-31.5,0 | +X | +Z |
| C3 | 左上环视相机 | -16,+55,+20 | +Z | -X |
| C4 | 左下环视相机 | -16,+55,-20 | -Z | +X |
| C5 | 右上环视相机 | -16,-55,+20 | +Z | -X |
| C6 | 右下环视相机 | -16,-55,-20 | -Z | +X |
| I0 | IMU | -18,0,0 | 不适用 | IMU三轴与B一致 |

上下相机只是在X/Y位置上对齐，光心相距40 mm，不是共用一个光心。四目的上下方向与滚转角是对组成图的一种明确建模解释，待客户或供应商确认。

为什么先取这些值：本版中央壳体宽86 mm，侧壳宽24 mm，将侧壳中心放在±55 mm可使侧壳与中央壳连接；侧壳高度28 mm，投影中心取±20 mm，给名义投影点留下6 mm轴向外伸。后移16 mm让环视组位于侧壳中部，IMU后移18 mm让它靠近中央承载部位。以上只是这一版代理结构的内部一致性，不证明器件能够按该尺寸装配或无遮挡。

### 外参定义

相机光学坐标：x向图像右方、y向下、z沿光轴。采用列向量：

```text
p_B = R_B_C p_C + t_B_C
T_C_I = inverse(T_B_C) T_B_I
T_I_C = inverse(T_B_I) T_B_C
```

JSON/YAML分别提供`T_B_cameraOptical_m`、`T_cameraOptical_B_m`、`T_IMU_cameraOptical_m`、`T_cameraOptical_IMU_m`。矩阵按行存储；所有4×4矩阵中的平移单位为米。四元数全部明确标成wxyz。

USD Camera本地轴与相机光学轴不同：USD用+Y向上、-Z向前。因此文件同时给出`R_B_usd`和`q_B_usd_wxyz`，不要把`q_B_optical_wxyz`直接填进USD Camera：

```text
R_B_USD = R_B_C × diag(1,-1,-1)
```

`seven_camera_frames.urdf`只表示固定TF树，没有质量、惯量、物理碰撞或摄像机渲染定义，不能当作完整动力学机器人模型。

## 4. 结构文件与单位

| 文件 | 内容 | 单位 |
|---|---|---|
| seven_camera_rig_proxy.step | 本体、镜筒后部、散热占位与USB线束，独立命名零件 | mm |
| wearer_proxy.step | 椭球头部、头带与连接占位，独立命名零件 | mm |
| complete_occlusion_proxy.step | 上述所有零件，18个代理实体 | mm |
| complete_occlusion_proxy_mm.stl | 辅助网格，不保留装配名称，非权威模型 | mm |
| seven_camera_rig.usda | 代理结构网格、7个Camera prim、IMU安装Xform | m |
| inspection_scene.usda | 引用上述USD，增加基础观察场景 | m |
| seven_camera_layout_mm.dxf | 三视图、佩戴投影、基准点与标注 | mm |

STEP导入Isaac时必须使用正确的毫米到米转换。仅修改stage的`metersPerUnit`并不会自动重写原始几何坐标。本包USDA已经转换为米，无需再缩放0.001。图纸只是排版后的示意视图，不要通过截图量尺寸。

USDA中的`IMU`目前是安装坐标，不是已实例化的物理传感器。要生成IMU信号，后续需让该坐标与正确的运动刚体绑定，并创建实际IMU传感器或经验证的连续运动测量生成器。

### 遮挡层

`/SevenCameraRig`下有4个可独立开关的Xform：

| 层 | 内容 |
|---|---|
| Housing | 中央壳、侧壳、七个镜筒后部 |
| Accessories | 右侧散热占位、USB线束 |
| WearerMount | U形头带与左侧连接占位 |
| Wearer | 椭球头部 |

这些均是会遮挡相机的可渲染实体，不是只参与物理碰撞的透明碰撞壳。没有用不透明玻璃球或镜头盖封住相机投影点，防止人为造成全黑图像。未模拟镜片折射、入瞳移动、内部暗角、MTF和结构变形。

头部中心(-120,0,-25) mm，半轴(85,72,105) mm，是可调几何假人，不是人体测量标准。未包含鼻、耳、头发、颈部、肩膀、手臂；需要研究这些遮挡时另加对应模型。头带与外壳并未做制造、装配、刚度或舒适性验证。

## 5. 光学模型：缺失参数显式假设

C0：理想针孔，HFOV120°，1920×1080，方形像素、中心主点。名义f=554.256258 px；按此模型算得VFOV约88.51°。这不是实物镜头VFOV。

C1/C2：理想等距投影r=fθ，HFOV160°，1600×1300，f=572.957795 px。暂取径向全角160°、像面半径800 px为有效边界，并与矩形画幅相交；真实角落能否成像未知。此选择旨在避免仅因未给DFOV，就擅自允许超过180°的角落视线。

C3—C6：理想等距投影r=fθ；将组成图的220°暂解释为圆形成像全角。1080×960画幅内放直径960 px的成像圆，f=250.017947 px，主点(540,480)。圆外区域无效。220°不是普通针孔HFOV，也不是PDF已经冻结的要求。

所有内参均为名义设计输入，畸变真实标定未知。本版关闭景深，不包含运动模糊/ISP/压缩/噪声/曝光耦合等实物成像因素。不要用当前图像清晰度代表客户0.3—2.5 m清晰范围已经通过。

### Isaac鱼眼后端注意事项

本包为等距相机写入兼容的RTX `fisheyePolynomial` 属性：θ=A+Br+Cr²+Dr³+Er⁴，其中A=C=D=E=0，B=1/f，θ用弧度、r用像素。该兼容后端已弃用，仍需在实际Isaac版本进行渲染验证；在一般USD查看器里，鱼眼属性可能被忽略并退化为针孔。

NVIDIA Isaac Sim 6.0官方文档明确提示：`OmniLensDistortionLutAPI`在该版本中存在回退针孔的问题。因此本包没有启用LUT schema，也不把“相机prim成功加载”视为鱼眼有效性的证据。后续版本或驱动若改变支持情况，应更换经验证的投影后端，不可静默改成针孔继续计算覆盖率。

首次运行必须做角度靶点验证：在移除所有占位遮挡的条件下，对某一环视相机设置相对光轴0/30/60/85/95/105/115°的目标。0至105°应在有效圆内，115°应被排除。特别检查95°和105°，这能识别是否发生了背半球视线丢失。

本包`isaac_capture_once.py --projection-check C3`会生成这些目标和期望像素坐标。需在目标机检查实际图像；该脚本不会仅凭配置内容宣告投影测试通过。

## 6. 在Isaac中先打开、再采一组图

最直接的方法：File → Open，打开`models/inspection_scene.usda`。设备根节点为`/World/Rig`，七路相机位于`/World/Rig/Sensors/`。检查场景把C0光心放在世界坐标(0,0,1.6) m，仅为观察方便，不代表佩戴者真实高度。

也可在Isaac安装目录运行（将`/path/to/package`替换为解压路径）：

```bash
./python.sh /path/to/package/scripts/isaac_capture_once.py \
  --headless --occlusion worn \
  --output /path/to/package/isaac_output/worn

./python.sh /path/to/package/scripts/isaac_capture_once.py \
  --headless --occlusion body \
  --output /path/to/package/isaac_output/body

./python.sh /path/to/package/scripts/isaac_capture_once.py \
  --headless --occlusion ideal \
  --output /path/to/package/isaac_output/ideal

./python.sh /path/to/package/scripts/isaac_capture_once.py \
  --headless --projection-check C3 \
  --output /path/to/package/isaac_output/projection_C3
```

脚本使用USD与Replicator生成不同分辨率的render product，只保存单次图像，不生成30 FPS时序，不验证硬件同步，不生成IMU或SLAM结果。它已通过Python语法检查，但本构建环境没有Isaac RTX，目标机仍需验证。

没有配置实体质量、惯量或关节。本模型适合先做静态几何/光学验证；给父节点设定一串不连续的位置，并不能自动获得可信的惯性测量。

## 7. 后续测试怎么分层

**第一层：几何覆盖与遮挡。**对比ideal/body/worn；每路保存有效成像区域、设备遮挡、头带遮挡与头部遮挡。不能将无效成像圆外的黑边归类为结构遮挡。用球面等立体角采样评价多目覆盖，避免把等经纬度像素数或鱼眼像素数直接当成立体角。近场0.3/0.5/1/2 m应按各相机真实光心向测试点投射射线，不要把所有光心并到一个点而忽略基线。

**第二层：图像生成。**换成有纹理、有深度层次和闭环行走路线的场景；保持各路源图分开，并保存同一仿真时刻与同步组标识。确认鱼眼边缘、裁剪、外参方向和图像旋转都正确。原图平铺输出只是数据组织，不意味着要做全景融合。

**第三层：SLAM/VIO。**先确认所选算法支持的相机数量、鱼眼模型、有效区域与IMU格式。可以先以一组可用双目/IMU跑通管线，再扩展多目联合方案；不能把七路画面机械塞给只接受双目的接口。纯转头试验不足以检验所有建图条件，应加入连续平移和转动。仿真真值轨迹/深度只用于ATE/RPE或地图评价，不可作为算法输入后再把结果称为SLAM建图能力。

PDF原始IMU下限为200 Hz。若使用600 Hz物理步进，30 Hz图像每20步、200 Hz IMU每3步可在同一仿真时间网格上调度；这是一个便于实现的仿真方案，不是新增客户要求。1000 Hz属于待确认的图示意图，不能通过重复或插值200 Hz数据制造“1000 Hz原始样本”。

本包没有固定通过阈值，没有编造SLAM建图精度，也没有承诺100%全向覆盖。先得到每路图像和遮挡分布，确认结构布置后再开展完整算法比较。

## 8. 可参数化修改与重建

源参数：`config/layout_parameters.json`。63 mm前向基线与中点关系应保留。环视间距、前后偏置、上下高度、IMU位置、前向俯角、头部尺寸、壳体/附件占位可作为设计变量；修改传感器姿态时应同时检查相应镜筒和支架是否仍合理。

可用的初始扫描集合（均为试验变量，不是制造公差）：环视横向间距100/110/120 mm；上下间距30/40/50 mm；环视后移8/16/24 mm；头部尺寸0.9/1.0/1.1倍。本版没做这些扫描，不能预判哪一组最佳。

普通Python环境重建CAD与外参（不要为了重建CAD去修改Isaac自带Python依赖）：

```bash
python -m pip install numpy scipy PyYAML cadquery ezdxf reportlab
python scripts/build_models.py
python scripts/build_drawings.py
python scripts/validate_layout.py
```

`build_drawings.py`需要环境中可用的中文字体；交付PDF已嵌入所需字形，不依赖接收方安装字体。源码的版式和标注针对当前SIM-V0.1基线，改变参数后必须同步检查图纸标注与数值，不能只更新CAD就继续发旧PDF。

## 9. 已验证与未验证

本次构建执行了90项离线检查，全部通过，包括：63 mm/中点关系、上下X/Y对齐、旋转矩阵正交与右手性、四元数与矩阵一致、相机/IMU双向外参、光心不在不透明实体内部、名义射线单位化、18个代理实体有效性、STEP回读、DXF审计、URDF固定TF结构和JSON/YAML一致性。

`validation/offline_validation.json`记录详细项目。对USDA只做了相机数量/单位等文本检查；此处没有安装pxr解析器，也没有NVIDIA Isaac运行环境。**USD运行时解析、RTX鱼眼效果、时序采集、IMU、SLAM/VIO、真实硬件全部未验证。**源文件在目标机出现错误时应显式停止，不能自动降级并继续输出看似有效的覆盖结果。

## 10. 来源

客户文件：`sources/customer_requirements_V0.2.pdf`的第2页§3，第4页§6.2/6.4，第6页§9，第7页§11；组成图见`sources/device_composition.jpg`。

下列官方资料仅用于坐标/API/投影后端说明，不用于增加客户需求（2026-09-18查阅）：

```text
NVIDIA Isaac Sim 6.0 Camera Sensors
https://docs.isaacsim.omniverse.nvidia.com/6.0.0/sensors/isaacsim_sensors_camera.html

NVIDIA Isaac Sim Conventions
https://docs.isaacsim.omniverse.nvidia.com/latest/reference_material/reference_conventions.html

NVIDIA Omniverse Cameras
https://docs.omniverse.nvidia.com/materials-and-rendering/latest/cameras.html

NVIDIA Isaac Sim 4.5 camera-model equations (legacy f-theta formula only)
https://docs.isaacsim.omniverse.nvidia.com/4.5.0/sensors/isaacsim_sensors_camera.html
```
