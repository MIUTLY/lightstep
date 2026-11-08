# 原始素材归档

states.zip为用户提供状态包的字节一致副本，已入仓。

receipts.zip为用户提供的票根(1).zip，31,351,571字节。其Git大文件上传被中断，原包仍完整保留在交付工作区及用户原附件中，本轮不重复长时间传输，不纳入Git。工作区备份：/workspace/deliverables/lightstep-original-receipts.zip。SHA256见../manifest.json的originals.receipts.zip.sha256。

线上运行不依赖原始ZIP，只需已入仓的v1运行图和manifest.json。需要重建时，把原始票根附件复制为本目录receipts.zip，再安装requirements-assets.txt并运行scripts/prepare_assets.py。

普通运行回归会明确跳过缺少外部票根原包时的源文件审计；状态原包、运行图哈希/HTTP/透明格式、日期配置和所有业务测试仍执行。交付工作区已对两包源文件完整核对。
