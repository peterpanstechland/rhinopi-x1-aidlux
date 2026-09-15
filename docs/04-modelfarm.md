# 模型广场（撰写中）

NPU 模型的统一入口，不是 YOLO 附录。

## 相关资料

- [模型广场](https://aiot.aidlux.com/zh/models)
- [Model Farm 用户指南](https://docs.aidlux.com/guide/software/ai-platform-portal-modelFarm)
- [MMS](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/ai-dev/model-farm/model_farm_mms)
- 本仓库目录：[modelfarm-catalog.md](modelfarm-catalog.md)

## 这一章要做的事

1. 注册阿加犀开发者账号（浏览免登录，下载要登录）
2. 网页筛选：芯片 `Qualcomm QCS8550`，精度优先 `INT8`
3. 读性能卡：设备、QNN 版本、**纯推理耗时**、精度损失、体积
4. 下载：网页「模型 & 代码」，或板上 `mms login` / `mms list` / `mms get`
5. 预览区（「联系我们」）只能 MMS
6. 按官方包 README 对齐 `aidlite-qnnxxx`，跑自带 `run_test.py`
7. 主线先跑通一只检测模型；联调板已有 YOLOv5s W8A8 QNN236，可先打通

详细步骤、截图和 `mms` 实测等你注册账号后补。
