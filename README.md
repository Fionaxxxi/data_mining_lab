# �����ھ�γ�ʵ��

�ֿ⣺[Fionaxxxi/data_mining_lab](https://github.com/Fionaxxxi/data_mining_lab)����ʽ���밴ʵ���ŷ�Ŀ¼���������Markdown��

## �����￪ʼ

| ʵ�� | ����Ŀ¼ | ���� | ���λ�� | һ������ |
|---|---|---|---|---|
| һ�����ݲɼ���Ԥ���� | [src/lab1/](src/lab1/) | [ʵ��һ����.md](ʵ��һ����.md) | `outputs/cleaned_data.*`����������ļ� | `.\run.ps1 -Lab 1` |
| ����ʵ��ʶ�� | [src/lab2/](src/lab2/) | [ʵ�������.md](ʵ�������.md) | `outputs/lab2/` | `.\run.ps1 -Lab 2` |
| �ģ���ָ���� | [src/lab4/](src/lab4/) | [ʵ���ı���.md](ʵ���ı���.md) | `outputs/lab4/` | `.\run.ps1 -Lab 4` |
| �壺���������������ȡ | [src/lab5/](src/lab5/) | [ʵ���屨��.md](ʵ���屨��.md) | `outputs/lab5/` | `.\run.ps1 -Lab 5` |

`run.ps1 -Lab all`��һ�������ġ���˳��ִ�У�ʵ���������ڶ�����`ʵ����/`Ŀ¼����ǰû�п��õ�ͳһ������ڣ���������`all`�С�ʵ��һĬ��ʹ���ѱ���ԭ��������ϴ����������ȡ��վ��ʵ������к��Զ����ʵ��λ�úʹ����԰�����

## ÿ���ű�����ʲô

| λ�� | ְ�� | ��ʱʹ�� |
|---|---|---|
| `src/lab1/crawl_official.py` | ����ٷ�·��ҳ�棬�������ģ�����HTML����ʵ�ɼ���¼ | ��Ҫ���²ɼ�����·��ʱ |
| `src/lab1/prepare_data.py` | ��Parquet����ȡ15ƪѡ���μǣ��ϲ�3�ݹٷ�·�� | ��Ҫ�ؽ�ԭʼ����ʱ |
| `src/lab1/preprocess.py` | ������ϴ18�ݲ��ϣ�����CSV/JSONL����������� | ʵ��һ��ʽ������� |
| `src/lab1/tools/inspect_source.py` | �鿴�׸���Ƭ�ֶμ���ѡ���� | ��ѡ̽�����ߣ��ճ����ܲ���Ҫ |
| `src/lab1/tools/scan_candidates.py` | ��������Ƭ���к�ѡ��ɸ | ��ѡ̽�����ߣ��ճ����ܲ���Ҫ |
| `src/lab2/entities.py` | ʶ��POI����ͨ��ʱ��ʵ�壬����λ�á�ͳ�ơ������������Ƶͼ | ʵ�����ʽ������� |
| `src/lab2/check.py` | ���ʵ����ԭ��λ�á���Դ���Ǽ��������� | ʵ��������� |
| `src/lab4/coref.py`��`figures.py` | ���ʼ�⡢���⡢�˹�����ͳ�Ƽ���ͼ | ʵ������� |
| `src/lab5/extract.py`��`finalize.py`��`figures.py` | ���������ѡ������ӳ�䡢����ͳ�Ƽ���״ͼ | ʵ������� |
| `archive/lab1/` | ��Word���ɴ��롢ģ�塢�ݸ塢��ͼ�;�ѹ���� | ��ʷ�鵵������������ʵ������ |

## ����������

��ǰ�������ʹ�ñ���Ŀ�� Python 3.11 ���� `D:\uniproject\data_mining\.venv`��ʵ���ġ������ʽ�ű�ֻʹ�ñ�׼�⡣

```powershell
Set-Location 'D:\uniproject\data_mining\data_mining_lab-main\data_mining_lab-main'
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Lab 5
```

�����в�����ʱ��

```powershell
py -3.11 -m venv D:\uniproject\data_mining\.venv
& D:\uniproject\data_mining\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

��Ҫ��������ʵ��һ�Ĳɼ��Ͳ���׼��ʱ������ִ�У�

```powershell
$py = 'D:\uniproject\data_mining\.venv\Scripts\python.exe'
& $py src\lab1\crawl_official.py
& $py src\lab1\prepare_data.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Lab 1
```

����֧��`--offline`��ֻ�������п��գ�����������Ҳ����Ϊһ���µĳɹ����ء����������¼��`data/source/crawl_manifest.json`��������־�������档

## ������ʵ���ν�

| Ŀ¼���ļ� | ���� |
|---|---|
| `data/source/` | ����ԭʼParquet��Ƭ�������ٷ�ҳ��HTML����Դ/�ɼ���¼ |
| `data/raw/selected_raw.jsonl` | ʵ��һѡ�е�18��ԭʼ���� |
| `outputs/cleaned_data.jsonl` | ʵ��һ��ϴ�����Ҳ��ʵ���������ʵ���ͳһ�ı����� |
| `outputs/quality_report.json` | ʵ��һ����������ȱʧ���ظ�����ʽ���ݵȼ�� |
| `outputs/cleaning_audit.csv` | ʵ��һ������ϴ��� |
| `outputs/lab2/entities.json`��`entities.csv` | ʵ���ʵ�塢�淶������Դ���ַ�λ�� |
| `outputs/lab2/stats.json`��`iteration.json`��`frequency_*.svg` | ʵ���ͳ�ơ���������������Ƶͼ |
| `outputs/lab5/mapping.json`��`mapping.csv`��`stats.json` | ʵ���徭�����˶Ե�����������ӳ�估����ͳ�ƣ�С���˹����� `outputs/lab5/�˹�����¼.md` |

����·�������ȶ�������Ŀ¼�������ı���ϴ�ı���ʵ��λ�á����Ƭ�ͺ�ѡJSONLͨ��Git LFS���棬��¡��ִ��`git lfs pull`��ȡ�������ݡ�

��������[BAAI/IndustryCorpus2](https://modelscope.cn/datasets/BAAI/IndustryCorpus2)���ε������ķ�Ƭ���Լ���ɽ����կ������������Դ�ٷ���������������·�ߡ�15ƪ�μ�ȱ��ԭ��ҳURL������ԭ��¼ID����Ƭ���кţ���������Դ����ʷƱ�ۡ�����״̬�Ͳ�����Ϊ��������ֱ��������ǰ���ν��顣

`archive/lab1/`�еĲ��ϱ����������ļ�����ͳ�ƣ��鿴��ʽʵ��������ʹ�ø�Ŀ¼ Markdown �����`outputs/`���Ժ�����ʵ�鰴��ż�����֯��
