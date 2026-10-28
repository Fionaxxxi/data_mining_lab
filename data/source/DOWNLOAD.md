# 原始分片下载说明

数据集：BAAI/IndustryCorpus2，ModelScope master。2026-10-28观察到仓库提交228165f30a56b40ca8aea38d88ba58046a2428ea；复核时应比较manifest.json中的SHA-256，不能仅凭文件名确认相同版本。

仅下载两个指定文件，未遍历旅游网站，未编写爬虫。以下为精确文件下载URL：

https://modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo?Revision=master&FilePath=tourism_geography%2Fchinese%2Fhigh%2Frank_00130.parquet

https://modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo?Revision=master&FilePath=tourism_geography%2Fchinese%2Fmiddle%2Frank_00712.parquet

分别保存为data/source/rank_00130.parquet与rank_00712.parquet。首次文件约92 MB，第二个约505 MB。若master内容变化导致哈希不符，请使用记录版本或先明确更新后的样本，勿覆盖统计后仍使用旧报告数字。

官方页面快照只作为少量补充来源证据。选中范围由prepare_data.py定位，清洗输入全部另存为data/raw/selected_raw.jsonl。张家界一日游人工摘录见data/raw/official_zhangjiajie_excerpt.txt，原URL见README.md。
