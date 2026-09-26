# scripts/dev — 一次性调试脚本

本目录存放本 fork 开发过程中使用的调试/验证脚本。它们**不是构建基础设施**,不参与 CI,也不被任何其他代码引用。保留仅为复现历史调试过程。

三个脚本都服务于同一个 fork 改动:**发帖页面编辑区与预览区左右分栏**(提交 `228ba13fd`)。

| 脚本 | 作用 | 运行环境 |
|---|---|---|
| `check_layout.py` | 纯离线计算器。按 Bootstrap 3.3.6 断点算出各视口下分栏的实际像素宽度 | 任意 Python 3,**无需 Django/数据库/Docker** |
| `check_split_css.py` | 端到端冒烟测试:编译 `posting-split.less` → 登录超级用户 → 抓取发帖页 → 断言 6 个 DOM 标记 → 注入 CSS 导出 HTML → 烟测 `/api/preview-markup/` | **必须在 Docker 容器内**运行 |
| `extract_css.py` | 从 `check_split_css.py` 导出的 HTML 中抽取含 `.posting-split` 的 `<style>` 块 | **必须在 Docker 容器内**运行 |

## check_layout.py

```bash
python3 scripts/dev/check_layout.py
```

断点规则硬编码在 `layout_for()` 中,需与 `frontend/src/style/misago/posting-split.less` 的媒体查询保持同步:

| 视口 | 布局 | 表单 / 预览 |
|---|---|---|
| < 992px | 上下堆叠 | 100% / 100% |
| 992–1199px | 左右分栏 | 60% / 40% |
| 1200–1599px | 左右分栏 | 65% / 35% |
| ≥ 1600px | 左右分栏 | 60% / 40% |

**改了 less 里的媒体查询就要同步改这里**,否则这个脚本会给出错误结论。

## check_split_css.py / extract_css.py

两者都硬编码容器内绝对路径(`/app`、`/tmp`),只能在 `misago` 服务容器里跑:

```bash
docker compose exec misago python /app/scripts/dev/check_split_css.py
docker compose exec misago python /app/scripts/dev/extract_css.py
```

### 未声明的依赖

`check_split_css.py` 需要 **`lesscpy`**,而它**不在 `requirements.in` / `requirements.txt` 中**。运行前需手动安装:

```bash
docker compose exec misago pip install lesscpy
```

### 前置条件

- 数据库已迁移,且存在至少一个用户(脚本用 `is_superuser` 优先,否则取任意第一个用户)
- 存在 slug 为 `first-category`、id 为 `3` 的分类 —— URL `/c/first-category/3/start/` 是硬编码的。可用 `./dev loaddevfixture` 或 `./dev fakedata` 准备数据

### 副作用

`check_split_css.py` 会**写文件**:`/app/posting_split_preview.html`(约 1.9MB)。该产物已加入 `.gitignore`,不应提交。`extract_css.py` 只读不写。

## 历史备注

原先根目录下还有 `check_split_css.py.bak` 和 `extract_css.py.bak`,是同一提交 `228ba13fd` 中被取代的旧草稿(`extract_css.py` 的旧版用单次 `re.search` 取第一个 `<style>` 块,现行版用 `finditer` 精确匹配含 `.posting-split` 的块)。已删除,内容可从该提交取回:

```bash
git show 228ba13fd:extract_css.py.bak
```
