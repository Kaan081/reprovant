# Third-party notices

## Eventflow — modified task demonstration

- Upstream repository: https://github.com/juneja-varun/eventflow
- Pinned upstream commit: `c08455d626d5e1c316d932c4da0652086fb1b19e`
- Original source: `orders/tasks.py`
- Modified derivative included here: `experiments/eventflow_guarded/tasks_guarded.py`
- Modification: guard a `PENDING`-only status transition with a conditional database update, and publish the event only for a successful transition.
- Upstream license: **MIT**. The notice below is retained from upstream `LICENSE` at the pinned revision.

The upstream project and original portions of the task implementation are copyright of their respective author(s). This repository does not claim ownership of those original portions.

### Upstream MIT license text

MIT License

Copyright (c) 2026 Varun Juneja

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Other external demonstrations

The external ETL repository `timur-rimsky/api-airflow-postgres-etl-pipeline` and the full Eventflow repository are **not vendored** in the tracked source tree. Workflows download pinned upstream revisions into disposable test environments. This statement does not grant rights to redistribute upstream projects; check their own license terms separately.

## Reprovant license and upstream rights

The root [Apache-2.0 LICENSE](../LICENSE) applies to original/author-owned Reprovant material. It does **not** erase the separate MIT copyright notice and permission terms above for the Eventflow-derived sample. Retain those notices when redistributing copies or substantial portions of that sample.
