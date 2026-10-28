# 原始分片下载说明

数据集：BAAI/IndustryCorpus2，ModelScope master。2026-10-28观察到仓库提交228165f30a56b40ca8aea38d88ba58046a2428ea；复核时应比较manifest.json中的SHA-256，不能仅凭文件名确认相同版本。

语料分片按以下两个固定文件URL下载。官网路线由`src/lab1/crawl_official.py`定向爬取，采集方式和运行入口见README.md。

https://modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo?Revision=master&FilePath=tourism_geography%2Fchinese%2Fhigh%2Frank_00130.parquet

https://modelscope.cn/api/v1/datasets/BAAI/IndustryCorpus2/repo?Revision=master&FilePath=tourism_geography%2Fchinese%2Fmiddle%2Frank_00712.parquet

分别保存为data/source/rank_00130.parquet与rank_00712.parquet。首次文件约92 MB，第二个约505 MB。若master内容变化导致哈希不符，请使用记录版本或先明确更新后的样本，勿覆盖统计后仍使用旧报告数字。

官方路线由src/lab1/crawl_official.py定向采集并提取，三份HTML快照和crawl_manifest.json保留实际请求证据。prepare_data.py合并语料与爬虫输出，清洗输入另存为data/raw/selected_raw.jsonl。张家界实际使用武陵源新闻网的官方机构署名原发页面，地址见README.md。旧人工摘录文件仅为程序全部网络及快照来源不可用时的备用材料，不计入本次采集结果。
