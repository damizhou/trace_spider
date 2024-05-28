# 代理流量收集

用来收集代理流量

## 部署步骤
1. 克隆项目
```
git clone https://github.com/damizhou/trace_spider.git
```
2. 修改配置文件`config.ini`文件，主要修改其中单个URL爬取时间。
3. 下载Dokcer镜像
```
docker pull chuanzhoupan/trace_spider:0527
```
4. 运行docker, 根据自己的实际情况修改`--volume`参数，`F:\trace_spider`为克隆项目的路径。挂载部分包含脚本代码，不挂载脚本无法正常运行。
```
docker run --volume F:\trace_spider:/app --privileged -itd --name my_trace_spider chuanzhoupan/trace_spider:0527 /bin/bash
```
5. 关闭网卡合并包

```
sudo ethtool -K docker0 tso off gso off gro off
```
6. 进入容器
7. 关闭网卡合并包
```
sudo ethtool -K eth0 tso off gso off gro off
```
8. 修改url_list.txt中的需要爬取的URL列表
9. 运行程序，在`app`下执行
```
python main.py
```