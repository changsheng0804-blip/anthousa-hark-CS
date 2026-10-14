# 户籍旁车 reg/{40,50,60}/{tx}_{ty}.json

来源：刘线（liuzhijie820802-a11y/anthousa-liuzhijie）liu/main 8034184，experiments/city_system_v6/tiles_join/reg/；记录内容一字未改。
由刘线 city_system v6 按 world.json 生成（区、教区、供水组由账本推出；坊、哨、职务是刘线的模型假设）。
装箱：tools/cs/factory/reg_pack.py 按我们瓦片 vec 里每栋房的底账 id（h[5]）重新分文件，只装那一年站着且刘线有记录的户。
CS 瓦片页只在敲门卡点开时才懒取这栋房所在瓦片的一个文件，按 id 找这户；找不到的房子不显示这一行。
