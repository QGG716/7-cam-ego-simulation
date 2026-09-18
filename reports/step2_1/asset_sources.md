# Step 2.1 官方资产来源

- 环境文档：[Isaac 6.0 Office / Hospital](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/assets/usd_assets_environments.html)、[6.1 对照](https://docs.isaacsim.omniverse.nvidia.com/6.1.0/assets/usd_assets_environments.html)。实际使用既有 6.0.1.0 安装，未升级。
- 人物文档：[Male Doctor](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/assets/usd_assets_props.html)。
- 安装接口：`isaacsim.storage.native.get_assets_root_path()`，实际解析根目录 `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0`。
- Office：根目录 + `/Isaac/Environments/Office/office.usd`，HTTP 200、USD 实际加载；Z-up，metersPerUnit=1，defaultPrim=/Root。
- 文档原样 `.../origial_male_adult_medical_01/...` 在本资产版本 HTTP 404 / Omni Client ERROR_NOT_FOUND；仅列举官方 Characters 目录后，核实实际为 `/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd`，HTTP 200，USD 实际加载。此更正基于实际目录证据，并非默默改写拼写。
- 人物也是 Z-up、metersPerUnit=1，含完整蒙皮人物、衣服、鞋及骨骼；无站立动画。仅在本轮覆盖层修改两侧上臂骨骼旋转，冻结静态姿态。
- 蒙皮测量依据：[OpenUSD 25.11 Python SkinningQuery 绑定](https://github.com/PixarAnimationStudios/OpenUSD/blob/v25.11/pxr/usd/usdSkel/wrapSkinningQuery.cpp)，使用 ComputeSkinningTransforms 与 ComputeSkinnedPoints，按最终姿态的实际顶点测量，未用旧 extent 代替。

仅按场景引用加载必需的 Office Props、材质和贴图，以及医生的材质贴图；未下载完整资产全集。官方 USD 均通过只读 HTTPS 引用加载，复用 Omni Client/Kit 缓存。工程内 `.cache/step2_1/posed_vertices.npz` 仅为私有测量缓存，不发布。最终用到的 USD 依赖列表见 `loaded_layers.json`；具体贴图加载结果与警告记录在本轮 Isaac 日志和报告中。

官方原始 USD、材质、贴图、蒙皮顶点和缓存不进入公开仓库；公开部分只包含引用覆盖层、安装与姿态设置、运行代码、测量摘要及本轮渲染结果。使用者应遵守 NVIDIA 资产附带条款，代码仓库不转授这些资产的许可。

本次运行核实 Kit 的可复用缓存目录为既有 Isaac 安装下 `kit/cache`（约 2.7 GB 总缓存，含既有内容，不能把这个总量当作本轮下载量）。本轮日志未修改该目录之外的其他项目。
