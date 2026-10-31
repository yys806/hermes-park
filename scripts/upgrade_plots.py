"""园区模型返工流水线：按优先级逐块修复/加细节，跑完自动验收并更新查看器。

用法：python upgrade_plots.py [--only=task1,task2] [--stop-after=N]
"""
import json, os, re, shutil, struct, subprocess, sys, time, uuid, socket
from datetime import datetime

HOME = r"D:/hermes/home"
OUT = os.path.join(HOME, "out", "models")
VIEWER = os.path.join(HOME, "viewer", "models.json")
REPORT = os.path.join(HOME, "out", "报告-返工.md")
TASKS_DIR = os.path.join(HOME, "prompts", "upgrade")

TOOLS = ("mcp__blender__execute_blender_code,mcp__blender__look,"
         "mcp__blender__get_scene_info,mcp__blender__get_addon_status,Read,Write,Edit")

COMMON = """
【通用要求（每轮都适用）】
- 绝不能用 read_factory_settings / read_homefile（会断开 MCP）。
- 只改指定场景，不要动其它场景。
- 每隔几步保存一次 D:/hermes/home/out/models/all_plots.blend。
- 每次 execute_blender_code ≤ 70 行，一类一类做，每完成一类 look 看一眼。
- 导出：只导本场景，顶点色层名 AO，贴图清空，名字不要带 .001 / .ct 后缀。
- 所有几何体必须在 ±{half} 米内。

【精度基准：对齐学习科研和日常事务】
- 文件 15 MB 以上、三角面 50 万以上、材质 60 个以上。
- 每样东西都要像"装出来的"：窗有窗框/窗台/窗棂/玻璃分格；门有门框/门板分块/门把/门槛；
  屋顶有瓦垄/檐口/屋脊/包边；地面铺装分块有缝、有路缘石；家具道具带零件（腿、抽屉、拉手、螺栓）。
- 暗部靠 AO 顶点色（导出 COLOR_0），不要靠材质自发光。
- 卡通黏土风：大圆角、哑光、低饱和、柔和光；贴图一律不用。

【绝对不要渲染】
- 三次崩溃都发生在 Cycles 渲染出图之后，所以本轮一律不渲染。
- 本提示词里凡是写着"渲染 xxx.png"的，全部跳过，不要执行。
- 自检只用 mcp__blender__look 看视口截图，不要调用 render。
- 做完直接导出 glb，图片我另外用独立进程统一出。

【直接动手】这是执行任务，不是让你写计划。不要输出步骤清单、不要复述要求，
每一条都立刻用工具实际执行，做完再简短汇报结果。
"""


TASKS = [
    # ---------- 第一优先：家人事务没颜色 ----------
    dict(id="family", scene="family", size=16, name="家人事务",
         prompt="""【返工原因】这块地 49 个材质的底色全是 0.8/0.8/0.8 同一个灰，整块地没有颜色。

【必须做】
1. 按设计把每个材质改成它该有的颜色（低饱和、明亮、哑光），参考配色：
   - 青灰石砌墙 #B9BCB6、浅灰坡顶 #8C8F8A、铜色大门 #A9784E
   - 白墙 #F0EDE6、浅蓝屋顶 #A8C4D4、淡红十字符 #D98B8B
   - 浅灰瓷砖 #D8D6D0、广场铺装 #CDCCC6、草绿 #86A96A、白篱笆 #F5F3EE
   - 长椅暖木 #B98F5F、引导线白 #F2F0EA
   每个材质都要设 roughness 0.9、metallic 0、specular 0。
2. 颜色改完之后必须逐材质核对一遍，确认没有两个不相关的部件共用同一个色（比如墙和草同色）。
3. 顺带把细节补到基准量级：档案馆的小拱窗要窗框+窗棂+玻璃分格、铜门要有门钉和门环、
   医院要有蓝色雨棚的支架、办事大厅三个服务窗口要有开口和牌子、取号机要有屏幕和小按键。
4. 灯补到 4 盏：档案馆门前、医院门前、办事大厅门前、南入口各一盏，
   命名 LGT_family_<灯名>，各自独立材质、各自一个点光源，只有灯罩发光。
5. 收尾：渲染 family_iso.png，导出 family.glb，打印材质清单（名字+色值）与包围盒。"""),

    # ---------- 第二优先：三个外协 ----------
    dict(id="clawd", scene="clawd", size=20, name="Claude 外协",
         prompt="""【返工原因】用户原话：「三个外协，我就只要一个具体的这个东西，不要别的装饰啥的」。
现在做得不像、而且加了键盘、纸堆、小方块这些多余配饰。

【必须做】
1. **删掉所有配饰**：键盘、纸堆、小方块、电线、名牌、地面散落物，全部删除。
   只保留：本体（橙色方块小螃蟹）+ 一块薄圆形底座。底座要薄、要干净，不要凹槽装饰。
2. **按设计把本体做准**：
   - 身体是横向厚实长方体，颜色橙红（熟番茄和赤陶之间，约 #C1492B），哑光
   - 脸上两只竖着的小黑点眼睛，左右间距不大
   - 下沿伸出四条短短的小方腿，均匀排列，同样是橙红倒角方块
   - 身体左右两侧各伸出一小截方块状小夹子，很短很平、微微朝前
   - 整体敦实方正，棱边大倒角但轮廓保持方正，绝不圆胖
3. **提高精度到基准量级**：给本体分件做细节——腿和身体之间要有接缝、夹子要有两节、
   眼睛要有微微凹陷的眼窝、身体侧板做成分块拼合的（能看出是几块拼的）、
   底座边缘做一圈细倒角。三角面做到 40 万以上，文件 6 MB 以上。
4. 灯：外协地块不需要路灯，但要在底座旁加一盏小地灯（矮柱+灯头，高 1.2 m），
   命名 LGT_clawd_lamp，只有灯罩发光。
5. 收尾：渲染 clawd_iso.png（正面一个、斜 45 度一个），导出 clawd.glb，打印清单。"""),

    dict(id="pi", scene="pi", size=20, name="Pi 外协",
         prompt="""【返工原因】用户原话：「三个外协，我就只要一个具体的这个东西，不要别的装饰啥的」。
现在做得不像、还加了标记牌、小方块、电线这些多余配饰。

【必须做】
1. **删掉所有配饰**：标记牌、小方块、电线、散落物，全部删除。只保留 P 形本体 + 一块薄圆形底座。
2. **按设计把本体做准**——三块低饱和色块拼成一个 P，三块厚度一致、都大倒角但保持块状：
   - 上方：鲑鱼粉（浅珊瑚粉，约 #E8A79B）的倒 L 形块，横片在上、竖片朝下，构成 P 的上半弧
   - 左侧：浅蓝（约 #A8C6DC）的不规则块，位于造型左下
   - 右下：淡黄（约 #E3D18A）的细长竖条，立在右下方
   - 三块之间留一点缝隙，看得出各自独立又能拼成 P
   - 绝不变成球或圆团，保持块状几何感
3. **提高精度**：三块都要做成有厚度、有倒角的多面体（不是简单拉伸）；
   块与块之间的缝隙要干净；底座加一圈细倒角。三角面 35 万以上，文件 6 MB 以上。
4. 灯：底座旁一盏小地灯，高 1.2 m，命名 LGT_pi_lamp，只有灯罩发光。
5. 收尾：渲染 pi_iso.png，导出 pi.glb，打印清单。"""),

    dict(id="codex", scene="codex", size=20, name="Codex 外协",
         prompt="""【返工原因】用户原话：「三个外协，我就只要一个具体的这个东西，不要别的装饰啥的」。
现在做得不像、还加了终端机、纸堆这些多余配饰。

【必须做】
1. **删掉所有配饰**：终端机、纸堆、散落物全部删除。只保留云本体 + 一块薄圆形底座。
2. **按设计把本体做准**：
   - 云由五六个大小不一的圆球挤在一起堆成，轮廓饱满柔和、全圆角
   - 颜色上浅下深渐变：顶部浅紫（#B9A8D8）、中间蓝紫（#7E7FC4）、底部深蓝（#4A5A9E），
     用分件不同色实现渐变，不要用贴图
   - 云的正前方居中浮着一个白色终端提示符号：一个向右的尖角箭头 + 一条短横线，
     白色、圆角、有轻微厚度，贴在云面上
3. **提高精度**：云要分 6-8 个球体件，球与球之间接缝自然；
   终端符号做成有厚度的实体（不是平面贴片），箭头和横线分开两件；
   底座加一圈细倒角。三角面 40 万以上，文件 7 MB 以上。
4. 灯：底座旁一盏小地灯，高 1.2 m，命名 LGT_codex_lamp，只有灯罩发光。
5. 收尾：渲染 codex_iso.png，导出 codex.glb，打印清单。"""),

    # ---------- 第三优先：中央大厅主体放大 ----------
    dict(id="control", scene="control", size=25, name="中央大厅",
         prompt="""【返工原因】用户原话：「中央这个，中间这个太小了，要很大！」现在中枢大厅在地块里占比太小，
而且总体精细度不够。

【必须做】
1. **放大主体**：圆形基座直径从 6 米放大到 **16 米**，穹顶从 5 米放大到 **13.5 米**，
   整体高度相应提高（基座 3 米 + 穹顶约 8 米，总高约 12 米）。
   八条轨道相应加长，从基座边缘向外铺到地块边界内 1 米处。
2. **提高精度**（目标 50 万面以上、15 MB 以上）：
   - 穹顶分瓣：做 8 片或 16 片弧形瓣，瓣之间有线脚缝
   - 两条环带上的小圆窗：每个窗要有窗框、内凹、玻璃分格
   - 门廊：四根圆柱要有柱础、柱身收分、柱头；拱门要有拱券分块石
   - 基座外壁的八组抽屉：每段 3 个，每个要有面框、拉手、能看出厚度
   - 八条轨道：每条要有轨道面、两侧挡边、挡边立柱、末端闸口拱帽，每条轨道上再加一段传送带
   - 监控台：四五块屏幕各带边框和支架，台面有分格
3. 灯保持 5 盏独立，但灯杆加细节（基座法兰+杆箍+灯笼笼条）；穹顶值守灯要明显。
4. 四季和雪层同步放大到新尺寸。
5. 收尾：渲染 control_iso.png、control_winter.png，导出 control.glb，打印八条轨道清单与包围盒。"""),

    # ---------- 第四优先：资产管理重做 ----------
    dict(id="vault", scene="vault", size=16, name="资产管理",
         prompt="""【返工原因】用户原话：「资产管理做的太差了，精细度不够，轨道这些都有问题」。

【必须做】
1. **先把轨道和传送带修对**：现在 Port_/Belt_ 走向不对、有断头、有的浮空或穿模。
   要求：六个实体（机房/中转信号塔/域名桩阵列/网站展示台/钥匙柜/三个小工位）各有一个 Port_，
   四条以上 Belt_Sub_ 都从实体脚下出、汇到 Belt_Hub_vault、再由 Belt_Main_vault 直奔正南
   Port_Main_vault；带子要贴地、支腿落地、接口有法兰和螺栓、汇合处有导流挡板。
2. **整块地提升精度到 50 万面以上、15 MB 以上**：
   - 机房：屋顶三个散热风扇要扇叶+护网+螺栓；侧墙大玻璃窗要有窗框和分格，里面两排机柜
     每个机柜要有指示灯、把手、通风孔；门口温度屏要有屏幕框
   - 中转信号塔：三圈环箍、三个抛物面碟（碟面+支架+馈源）、塔基圆台、底部一圈小窗
   - 域名桩阵列：四根柱子各有底座、柱身线脚、顶上门牌（带边框和刻线）、引出的线缆走地
   - 网站展示台：三个屏幕各带边框支架，台面分格、两个抽屉带拉手
   - 钥匙柜：六个抽屉各有面框、圆拉手、钥匙孔；柜顶钥匙串要能看出三把钥匙
   - 三个小工位：桌子有腿、横撑、桌面分格；椅子有靠背和四条腿；每桌一块名牌
3. 灯补到 4 盏，各自独立材质与点光源，只有灯罩发光，命名 LGT_vault_<灯名>。
4. 四季四套同步补齐，冬季要有地面雪、屋顶雪、道具顶雪。
5. 收尾：渲染 vault_iso.png，导出 vault.glb，打印 Port/Belt 清单、包围盒、面数。"""),
    # ---------- 其余四块：整体精修 ----------
    dict(id="clock", scene="clock", size=16, name="通知待办",
         prompt="""【返工原因】用户要求除学习科研、日常事务外全部精修到同等精细度（文件 15 MB 以上、50 万面以上）。

【必须做】在现有基础上加细节，不要重做布局：
1. 钟楼：四面钟盘各要有盘面、刻度、时针分针秒针、外圈边框、内圈玻璃；
   塔身要有分层线脚、转角壁柱、底部基座；顶上坡顶要有瓦垄和屋脊，方向标要能看出箭头。
   塔脚报亭：卷起的报纸要能看出纸卷、取报口要有边框、斜遮檐要有支撑。
2. 齿轮塔：三个齿轮要真的做出齿形（不是圆柱贴片），每个齿轮有轮毂和辐条；
   摇柄要有弯曲的关节和柄端圆球；小窗口要有窗框和里面的纸条。
3. 接单亭：翻页牌要做出两排翻页小块（每块有厚度）；投递口要有口沿边框；
   四坡顶要有瓦垄；小旗要有旗杆和旗面。
4. 广场：钟面图案要做成嵌进地砖的浅浮雕（同心圆+放射线有高差）；
   环形小路两侧路缘石分块；环形路本身要有铺装缝。
5. 灯补到 4 盏（钟楼前、齿轮塔旁、接单亭旁、南入口），命名 LGT_clock_<灯名>，各自独立材质与点光源。
6. 四季四套 + 冬季地面雪/屋顶雪/道具顶雪。
7. 收尾：渲染 clock_iso.png、clock_winter.png，导出 clock.glb，打印面数/材质数/包围盒。"""),

    dict(id="press", scene="press", size=16, name="咨询新闻",
         prompt="""【返工原因】用户要求除学习科研、日常事务外全部精修到同等精细度（文件 15 MB 以上、50 万面以上）。

【必须做】在现有基础上加细节，不要重做布局：
1. AI 资讯塔：三圈发光环要有凹槽和环箍；塔身收分要分段；塔顶圆球要有底座和托架；
   塔基一圈小指示灯要每颗有灯座。
2. 热点新闻台：五根细杆各要有底座、杆箍、顶部圆盘或三角旗（旗面要有厚度和旗杆）；
   台面上的报纸杂志要能看出是一摞一摞的（每摞分张）。
3. 工具库：大玻璃窗要有窗框和分格、里面两排架子每层要有立板和横板，
   架上的小工具（方块/齿轮/扳手/机器人头/灯泡）每样都要认得出；
   坡屋顶要有瓦垄和屋脊；门口木箱要有板缝和铁箍。
4. 分拣传送带：带面要有滚筒纹路、两侧挡边要有立柱、支腿要有底座、
   汇合处要有导流挡板、分拣台要有小屏幕和顶灯。
5. 喇叭亭：大喇叭要做出喇叭口和支架；亭内报纸摞要分张；小窗要有窗框。
6. 灯补到 4 盏，命名 LGT_press_<灯名>，各自独立材质与点光源。
7. 四季四套 + 冬季雪。
8. 收尾：渲染 press_iso.png、press_winter.png，导出 press.glb，打印清单。"""),

    dict(id="inventor", scene="inventor", size=16, name="奇思妙想",
         prompt="""【返工原因】用户要求除学习科研、日常事务外全部精修到同等精细度（文件 15 MB 以上、50 万面以上）。
**注意：不要改变包围盒，必须仍然是 16×16，所有几何体在 ±8 米内。**

【必须做】在现有基础上加细节，不要重做布局：
1. 歪塔：螺旋铜管要真的绕塔身多圈（每圈有管径、有接头）；塔身分节；
   塔顶半透明球要有托座和内部光源；塔基台座散落的零件（齿轮/螺丝/铜管）要认得出。
2. 疯实验台：漏斗要有锥面和管口；弯铜管要多段折弯；试管架要有立板和孔位、
   试管要有管口和液面；线圈要一圈圈能数出来；弹簧要能看出螺旋；吊灯要有灯罩和吊绳。
3. 半成品机器人：方脑袋要有面部开孔和天线；完整机械臂要有三段关节和手爪；
   半截臂要断口自然；脑袋歪的角度要明显。
4. 灵感罐架：玻璃罐要透明感（浅色+高光），罐内彩色云雾要做成多个球体团块；
   软木塞要有纹理感（分块），标签要有边框。
5. 表情墙：每块小方牌要有厚度和外框，表情用几何块拼出来（眼睛/嘴），排布要错落。
6. 弹簧发射台：四根弹簧要做成螺旋（能数出圈数）；中央拉杆要有球头；护栏要有立柱和横杆。
7. 灯补到 4 盏，命名 LGT_inventor_<灯名>，各自独立材质与点光源。
8. 四季四套 + 冬季雪。
9. 收尾：渲染 inventor_iso.png、inventor_winter.png，导出 inventor.glb，
   打印包围盒（必须是 16.0×16.0）、面数、材质数。"""),

    dict(id="rainbow", scene="rainbow", size=16, name="彩虹事务",
         prompt="""【返工原因】用户要求除学习科研、日常事务外全部精修到同等精细度（文件 15 MB 以上、50 万面以上）。
这块现在 26 MB、58 万面已经有量，但细节密度还不均匀，重点补薄弱的部件。

【必须做】在现有基础上加细节，不要重做布局：
1. 粉色主屋：窗要有窗框、窗棂、窗台、花箱；屋顶坡面要有瓦垄和屋脊；
   门要有门框、门板分块、门把、门槛；心形门牌要有木牌底和心形凸起；
   门口信箱要有投信口、门、锁扣。
2. 出路雷达：抛物面碟要有网格骨架和中心馈源；基座要有分节；天线要能数出几根；
   指示灯要有灯座。
3. 露天书房：木平台要有板缝；四根柱子要有柱础；两片挑檐要有檐口收边；
   书桌要有抽屉和桌腿；书架要有层板和侧板、书要一本本能看出；矮栏杆要有立柱和扶手。
4. 爱心雕塑：白色圆基座要有分块环；心形表面要有高光和倒角；旁边木牌要有牌面和支架。
5. 花坛：石沿分块、花要成簇；草地铺装边缘要有收边石。
6. 灯补到 4 盏，命名 LGT_rainbow_<灯名>，各自独立材质与点光源。
7. 四季四套 + 冬季地面雪/屋顶雪/道具顶雪。
8. 收尾：渲染 rainbow_iso.png、rainbow_winter.png，导出 rainbow.glb，打印清单。"""),

    dict(id="family2", glbfile="family", scene="family", size=16, name="家人事务-收窄尺寸",
         prompt="""【唯一任务：把宽度收回来】
上一轮做完后包围盒是 21.3×16 m，横向超出 5.3 米，要求必须 16×16。
1. 找出所有 X 方向超出 ±8 米的物件（围栏、树木、灯、附属小屋、地块边缘装饰），
   逐个往内移或用缩放收进 ±8 米；不要删掉主体建筑，也不要改布局顺序。
2. 收窄后要保证：档案馆、医院、办事大厅三栋主屋完整，围栏闭合无缺口，
   四季孪生件跟着一起移（Foliage_/Bare_/Snow_ 系列）。
3. 重新渲染 family_iso.png（960×720、采样 48），导出 family.glb。
4. 打印包围盒，必须是 16.0×16.0 左右（±0.5 以内）。
""")

    dict(id="clawd2", glbfile="clawd", scene="clawd", size=20, name="Claude 外协-补地台与蟹钳",
         prompt="""【只改三处，别动已经做好的本体细节】
1. 补一块干净的 20 x 20 米地台：薄板厚 0.2 米、浅米灰色、四边细倒角，表面不要任何装饰和凹槽；
   本体放在地台正中，原来那块小结圆底座可以保留在上面。
2. 两侧夹子改成张开的两瓣蟹钳：每一侧由"上钳 + 下钳"两片组成，两片之间留一道缝，
   钳尖微微向内收，钳根和身体之间有短臂连接，保持橙色倒角块状。
3. 眼睛做成微微内凹的圆角竖槽，槽里嵌一颗更深的圆角块，看着是"点"不是"条"。
4. 灯保持原样，放在地台一角。
5. 不要渲染，做完直接导出 clawd.glb，打印包围盒（必须 20 x 20）和面数。
"""),

    dict(id="pi2", glbfile="pi", scene="pi", size=20, name="Pi 外协-修复受损",
         prompt="""【重要：这一版被上一轮重跑弄坏了，现在只有 4.8 米、6 个材质、没有灯】
要求在现有三块本体基础上修复，不要推倒重建、不要删除现有几何。

1. 补一块干净的 20 x 20 米地台：薄板厚 0.2 米、浅米灰色、四边细倒角，表面无装饰。
   三块本体居中摆好，整体占地块中央约 10 米见方。
2. 恢复三块的配色与材质区分（现在只有 6 个材质）：
   上方倒 L 形块鲑鱼粉 #E8A79B，左侧块浅蓝 #A8C6DC，右下竖条淡黄 #E3D18A；
   三块都设 roughness 0.9、metallic 0、specular 0，块与块之间留缝。
3. 给三块加细节到 40 万面以上：每块做成有厚度的多面体，棱边倒角分两段，
   表面做出轻微不规则的块面感；块与块接触处做浅接缝；底座加一圈细倒角。
4. 补一盏地灯（矮柱 + 灯头，高 1.2 米），放在地台一角，命名 LGT_pi_lamp 及子件，
   只有灯罩发光。
5. 不要渲染，做完导出 pi.glb，打印包围盒（20 x 20）、面数、材质数、灯数。
"""),

    dict(id="control2", glbfile="control", scene="control", size=25, name="中央大厅-透明穹顶与内部环形循环",
         prompt="""【本轮只做四件事，不要动已经调好的体量、轨道和外观细节】

一、穹顶做成透明的
- 穹顶改成玻璃壳体：透明玻璃，极浅青白，约 0.75 透光，磨砂质感，通透但不糊。
- 玻璃穹顶必须有骨架：沿经线 16 条弧形肋、沿纬线 3 圈环箍，骨架用不透明浅灰金属色，
  这样玻璃才看得见形状。穹顶顶部值守灯保留，挂在骨架中心。

二、外圈窗户做成能看进去的
- 两条环带上的所有小圆窗，玻璃改成真透明（约 0.85 透光，不要发白、不要强反射盖住内部），
  窗框保留。从外面任意角度看，窗洞后面必须是通亮的室内，不能黑或一片反光。
- 窗户内侧要有窗台和窗套，能看出墙的厚度。

三、室内做一套环形循环
- 大厅正中做圆形循环带：直径约 9 米的环形轨道，沿圆周铺开，
  轨道上 12 个舱位（小的圆角方块载体，间隔均匀），命名 Loop_pod_01 到 Loop_pod_12。
- 轨道本身要细节：内外两圈导轨（有厚度、有槽）、下方一圈支腿和底座、内侧一圈挡边，
  轨道中心留空。
- 室内四周沿墙一圈操作台（分格、每格一块小屏幕），屏幕命名 Loop_screen_01 起，
  屏幕只做发光材质、不加灯。室内地面分块铺装、有环形拼花；室内四个承重柱和柱帽。

四、环形轨道正中心立"更"的本体（最重要）
- 导入模型 D:/hermes/media/jarvis-avatar/3d-model/geng-3d.glb（1 米高、带烘焙纹理），
  缩放到总高 4.5 米，站在核心台座正中、脚底贴台面，正面朝向大厅正门（南侧）。
- 导入后把部件改名成 Geng_body / Geng_head / Geng_arm_L 这类前缀；
  纹理必须嵌进 glb，不要外链图片；材质保留原贴图，不要改成纯色。
- 台座：一根圆柱台座（分节、带线脚）坐在环形轨道中心，顶上一圈浅光，
  台座命名 Loop_core_base，更的本体站在上面就是循环的核心。

【材质与命名（很重要）】
- 透明件必须用 glTF 能导出的透明材质（alphaMode=BLEND）。
- 透明材质名字必须以 Glass 开头：穹顶叫 Glass_Dome，窗户玻璃叫 Glass_Window，
  否则查看器会把它当黏土材质强制变不透明哑光。
- 玻璃 roughness 约 0.1、metallic 0，不要设成 0.9。

【收尾】
不要渲染。做完导出 control.glb，打印：玻璃材质名与透明度、Loop_ 与 Geng_ 物件清单与数量、
包围盒（25 x 25）、面数、材质数。
"""),

]


def blender_alive():
    try:
        s = socket.create_connection(("127.0.0.1", 9876), timeout=2); s.close(); return True
    except Exception:
        return False


def ensure_blender():
    if blender_alive():
        return True
    log("Blender 不在，重启中")
    exe = r"D:/hermes/home/tools/blender-4.5.9-windows-x64/blender.exe"
    work = os.path.join(OUT, "all_plots.blend")
    subprocess.Popen([exe, work, "--python-expr", "import bpy;bpy.ops.blendermcp.start_server()"], cwd=HOME)
    for _ in range(60):
        time.sleep(3)
        if blender_alive():
            log("Blender 已恢复"); return True
    log("Blender 重启失败"); return False


def log(msg):
    line = f"- `{datetime.now().strftime('%m-%d %H:%M')}` {msg}\n"
    open(REPORT, "a", encoding="utf-8").write(line)
    print(line.strip())


def glb_stat(pid, target):
    p = os.path.join(OUT, pid + ".glb")
    if not os.path.exists(p):
        return None
    d = open(p, "rb").read(); n = struct.unpack("<I", d[12:16])[0]; js = json.loads(d[20:20 + n])
    names = [x.get("name", "") for x in js["nodes"]]
    prims = [pr for m in js["meshes"] for pr in m["primitives"]]
    lo = [1e9] * 3; hi = [-1e9] * 3
    for nd in js["nodes"]:
        if "mesh" not in nd:
            continue
        tr = nd.get("translation", [0, 0, 0]); sc = nd.get("scale", [1, 1, 1])
        for pr in js["meshes"][nd["mesh"]]["primitives"]:
            a = js["accessors"][pr["attributes"]["POSITION"]]
            mn, mx = a.get("min"), a.get("max")
            if not mn:
                continue
            for k in range(3):
                lo[k] = min(lo[k], mn[k] * sc[k] + tr[k]); hi[k] = max(hi[k], mx[k] * sc[k] + tr[k])
    size = (round(hi[0] - lo[0], 1), round(hi[2] - lo[2], 1))
    mats = [m.get("name", "") for m in js["materials"]]
    tris = sum(js["accessors"][pr["indices"]]["count"] // 3
               for m in js["meshes"] for pr in m["primitives"] if "indices" in pr)
    cols = set()
    for m in js["materials"]:
        bc = m.get("pbrMetallicRoughness", {}).get("baseColorFactor")
        if bc:
            cols.add(tuple(round(v, 2) for v in bc[:3]))
    return dict(size=size, ok=abs(size[0] - target) < 1.0 and abs(size[1] - target) < 1.0,
                tris=tris, mats=len(mats), colors=len(cols),
                lamps=len([m for m in mats if m.startswith("LGT_")]),
                mb=round(os.path.getsize(p) / 1048576, 1),
                color=f"{sum(1 for pr in prims if 'COLOR_0' in pr.get('attributes',{}))}/{len(prims)}")


def watchdog():
    import threading
    def loop():
        while True:
            time.sleep(20)
            if not blender_alive():
                log("看门狗：Blender 掉了，重启")
                ensure_blender()
    th = threading.Thread(target=loop, daemon=True)
    th.start()


def main():
    os.makedirs(TASKS_DIR, exist_ok=True)
    only = None; stop = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")
        if a.startswith("--stop-after="):
            stop = int(a.split("=", 1)[1])
    watchdog()
    if not os.path.exists(REPORT):
        open(REPORT, "w", encoding="utf-8").write(f"# 返工报告\n\n开始：{datetime.now():%m-%d %H:%M}\n\n")
    done = 0
    for t in TASKS:
        if only and t["id"] not in only:
            continue
        if not ensure_blender():
            log("跳过全部：Blender 不可用"); break
        txt = t["prompt"] + COMMON.format(half=t["size"] / 2)
        txt = txt.replace("🔴", "")
        txt = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", "", txt)
        pp = os.path.join(TASKS_DIR, t["id"] + ".txt")
        open(pp, "w", encoding="utf-8").write(txt)
        glbf = t.get("glbfile", t["id"])
        before = glb_stat(glbf, t["size"])
        bak = os.path.join(OUT, "_bak", glbf + "_" + datetime.now().strftime("%m%d%H%M%S") + ".glb")
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        src = os.path.join(OUT, glbf + ".glb")
        if os.path.exists(src):
            shutil.copy2(src, bak)
        log(f"开始返工 **{t['name']}**（改前 {before['mb'] if before else '?'} MB / "
            f"{before['tris'] if before else '?'} 面）")
        t0 = time.time()
        glb_path = os.path.join(OUT, glbf + ".glb")
        mtime0 = os.path.getmtime(glb_path) if os.path.exists(glb_path) else 0
        tail = ""
        for attempt in range(1, 4):
            if attempt > 1:
                log(f"  第 {attempt-1} 次没改动，等 60 秒重试")
                time.sleep(60)
                ensure_blender()
            session = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                     f"hermes-upgrade-{t['id']}-{attempt}-{datetime.now():%m%d%H%M%S}"))
            sh = (f'cd /d/hermes/home && claude -p "$(cat {pp.replace(chr(92), "/")})" '
                  f'--session-id {session} --permission-mode acceptEdits --allowedTools "{TOOLS}"')
            try:
                r = subprocess.run(["bash", "-lc", sh], cwd=HOME, capture_output=True, text=True, timeout=5400)
                tail = ((r.stdout or "") + (r.stderr or ""))[-400:]
            except subprocess.TimeoutExpired:
                tail = "超时"
            mtime1 = os.path.getmtime(glb_path) if os.path.exists(glb_path) else 0
            if mtime1 > mtime0:
                break
            log(f"  ⚠️ 未改动：{tail[-150:].replace(chr(10), ' ') or '无输出'}")
        after = glb_stat(glbf, t["size"])
        # 防回退：变小、变单调、灯丢了，就回滚
        worse = False
        if after and before:
            # 候选版本先留一份，回滚也不丢证据
            cand = os.path.join(OUT, "_cand")
            os.makedirs(cand, exist_ok=True)
            shutil.copy2(src, os.path.join(cand, glbf + "_" + datetime.now().strftime("%m%d%H%M%S") + ".glb"))
            if after["mb"] < before["mb"] * 0.75:
                worse = True
            if before["lamps"] > 0 and after["lamps"] == 0:
                worse = True
            if after["tris"] < before["tris"] * 0.7:
                worse = True
        if worse and os.path.exists(bak):
            shutil.copy2(bak, src)
            log(f"  ⏪ 结果比改前更差（{after['mb']}MB/{after['colors']}色 → 原 {before['mb']}MB/{before['colors']}色），已回滚")
            after = glb_stat(glbf, t["size"])
        if after:
            ok = after["ok"] and after["mb"] >= 12
            log(f"  {t['name']} 改后 {after['size'][0]}×{after['size'][1]} m / {after['tris']:,} 面 / "
                f"{after['mats']} 材质 / {after['colors']} 种颜色 / 灯 {after['lamps']} / {after['mb']} MB"
                f" → {'✅达标' if ok else '⚠️仍不达标'}")
            if after["ok"]:
                d = json.load(open(VIEWER, encoding="utf-8"))
                for m in d["models"]:
                    if m["id"] == glbf:
                        m["status"] = "ready"
                json.dump(d, open(VIEWER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        else:
            log(f"  ❌ {t['name']} 没有产出 glb：{tail[-160:].replace(chr(10), ' ')}")
        log(f"  用时 {int((time.time()-t0)/60)} 分钟")
        done += 1
        if stop and done >= stop:
            break
    log("返工流水线结束")


if __name__ == "__main__":
    main()
