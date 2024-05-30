# 代理流量收集

用来收集代理流量

## 部署步骤
1. 克隆项目
```
git clone https://github.com/damizhou/trace_spider.git
```
2. 修改配置文件**config.ini**文件，主要修改其中单个URL爬取时间。
3. 下载Dokcer镜像
```
docker pull chuanzhoupan/trace_spider:0527
```
4. 运行docker, 根据自己的实际情况修改`--volume`参数，`/home/dataset/pcz/trace_spider`为克隆项目的路径。挂载部分包含脚本代码，不挂载脚本无法正常运行。
```
docker run --volume /home/dataset/pcz/trace_spider:/app --privileged -itd --name pcz_trace_spider chuanzhoupan/trace_spider:0527 /bin/bash
```
5. 关闭物理机网卡合并包，要找到自己的docker和对应的物理机桥接网卡
```
sudo ethtool -K docker0 tso off gso off gro off
```
6. 进入容器
```
docker exec -it pcz_trace_spider /bin/bash  
```
7. 关闭网卡合并包
```
sudo ethtool -K eth0 tso off gso off gro off
```
8. 修改url_list.txt中的需要爬取的URL列表
9. 运行程序，在`app`下执行
```
python main.py
```
10. `logs`目录下是日志，日志以日期分割。例如`20240528.log`、`20240529.log`
11. 数据储存在`data`目录下，不同的URL分别有一个文件夹保存。
    - 数据文件命名格式为**时间_URL.pacp**。例如**20240528102026_douban.com.pcap**为**2024年5月28日10点20分26秒**开始采集的**douban.com**流量。
12. `analyze`目录下是流量分析脚本
    - `flows_packets`需要修改代码中的本机IP，改为实际的本机IP