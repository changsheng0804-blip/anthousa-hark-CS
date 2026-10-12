# CS 线 · Hark（主干候选）

预览：https://changsheng0804-blip.github.io/anthousa-hark-CS/living/xerolophos/

三条线并行：tanxinhao 线主攻「画」，刘线主攻「人的规模」，CS 线是主干候选——只收两条线里所有者选中的东西，自己主攻「摸不到底」：任何一扇门都能问，问出来的每一句都从底账推演的那一家里来。

## 同步规则
1. 底账（world.json、proposals/、rules/、chronicle/、engine/）：只跟 tanxinhao 线，单向，不改。
2. 素材（voices.json、笔刷套件、画、声音）：所有者选中才拿，一件一件拿，提交说明写明来自哪条线、哪个提交。
3. 页面：CS 线自己长；别的线想要 CS 线的东西，同样按件挑。

## 已收
- 刘线 liu2（fa5f167）：干山上 371 户街坊闲话 + 流水线（tools/）。

## 版本
- cs1 · 敲门问话：每栋有人的房子都能敲门，挑一个人问八件事（从哪来、靠什么过日子、家里有谁、房子以前住过谁、城里出过的事、信哪一派、隔壁是谁、街坊怎么说）。答案只用页面 household() 推演的那一家和底账事件拼出来，不调用任何在线模型；「隔壁是谁」里的名字点了就飞过去敲那家的门，可以一直敲下去。快照：docs/living/cs1/。
  自查：`node tools/cs/check_talk.js`（需 jsdom），对建城 55 年 4263 栋房子里每个能说话的人问全部问题，13 万条回答零空值。

## 留言 · Inbox
给 CS 线的话写在本文件末尾，或在仓库开 issue。
