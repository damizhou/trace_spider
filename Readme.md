# 流量收集

用来收集流量

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
4. 运行docker, 根据自己的实际情况修改`--volume`参数，`your_code_path`为克隆项目的路径。挂载部分包含脚本代码，不挂载脚本无法正常运行。和`--name`参数，`your_container_name`是容器名称
  - windows
    ```
    docker run --volume your_code_path:/app --privileged -itd --name your_container_name chuanzhoupan/trace_spider:0712 /bin/bash
    ```
  - linux
    ```
    docker run --volume your_code_path:/app -e HOST_UID=$(id -u $USER) -e HOST_GID=$(id -g $USER) --privileged -itd --name your_container_name chuanzhoupan/trace_spider:0712 /bin/bash
    ```
5. 关闭物理机网卡合并包，要找到自己的docker和对应的物理机桥接网卡
```
sudo ethtool -K docker0 tso off gso off gro off
```
6. 进入容器
```
docker exec -it your_container_name /bin/bash  
```
7. 关闭docker网卡合并包
```
sudo ethtool -K eth0 tso off gso off gro off
```
8. 修改url_list.txt中的需要爬取的URL列表
9. 运行程序，在`app`下执行
   - 对于novpn的采集
    ```
    python main.py sever_location sever_os novpn
    ```
    sever_location 是采集物理设备位置
    sever_os       是采集物理设备
10. 系统
    例如
    ```
    python /app/main.py hz ubuntu24.04 novpn
    ```
    - 对于使用vpn的采集
    ```
    python main.py sever_location sever_os vpn_loaction vpn_type udp/tpc
    ```
    sever_location 是采集物理设备位置
    sever_os       是采集物理设备系统
    vpn_loaction   是vpn节点位置
    vpn_type       是vpn节点协议
    udp/tpc        是指clash配置中是否使用udp，没有类似配置默认就是tcp
    例如
    ```
    python main.py hz ubuntu24.04 jpn trojan udp
    ```
10. `logs`目录下是日志，日志以日期分割。例如`20240528.log`、`20240529.log`

## 注意事项

1. 数据储存在`data`目录下，不同的URL分别有一个文件夹保存。
	- 数据文件命名格式为**采集物理设备时间_URL.pacp**。pcap命名规则：收集设备物理位置_收集设备系统_vpn位置_vpn协议_tcp/udp_时间_网址
      - 例如**usa_ubuntu24.04_novpn_20241119_043213_comdirect.de.pcap**为位于**usa**系统为**ubuntu24.04**的物理设备**直接**收集的**2024年11月19日04点32分13秒**开始采集的**comdirect.de**流量。
      - 例如**hz_ubuntu24.04_sgp_trojan_udp_20241119_084114_07pbc.cc.pcap**为位于**hz**系统为**ubuntu24.04**的物理设备通过协议是**trojan**，节点在**sgp**的**vpn**收集的**2024年11月19日08点41分14秒**开始采集的**07pbc.cc**流量。
2. `analyze`目录下是流量分析脚本
   - `flows_packets`需要修改代码中的本机IP，改为实际的本机IP
3. 关闭网卡合并包，每次启动linux都要重新运行。包括物理机和docker

