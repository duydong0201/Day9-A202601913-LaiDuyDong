const select = document.querySelector("#case-select");
const status = document.querySelector("#status");
const summary = document.querySelector("#summary");
const result = document.querySelector("#result");
const issueLabel = (issue) => issue.replaceAll("_", " ");
const money = (value) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "BRL", minimumFractionDigits: 2 }).format(value);
async function request(path) { const response = await fetch(path); const data = await response.json(); if (!response.ok) throw new Error(data.error || "Không thể chạy agent."); return data; }
function showError(error) { status.textContent = `Lỗi: ${error.message}`; status.classList.add("error"); }
function showSummary(data) { summary.innerHTML = [`<article><strong>${data.total_cases}</strong><span>case sẵn sàng</span></article>`, ...Object.entries(data.issues).map(([issue, count]) => `<article><strong>${count}</strong><span>${issueLabel(issue)}</span></article>`)].join(""); }
function showCase(data) {
  const output = data.output; const assessment = output.assessment; const financial = output.financial_resolution;
  document.querySelector("#case-title").textContent = data.case.case_id;
  const badge = document.querySelector("#issue-badge"); badge.textContent = issueLabel(assessment.primary_issue); badge.className = `badge ${assessment.case_status}`;
  document.querySelector("#metrics").innerHTML = `<article><span>Trạng thái</span><strong>${assessment.case_status}</strong></article><article><span>Confidence</span><strong>${assessment.confidence}</strong></article><article><span>Hoàn tiền</span><strong>${money(financial.recommended_refund_brl)}</strong></article><article><span>Action</span><strong>${output.resolution_actions.join(", ")}</strong></article>`;
  document.querySelector("#handoffs").textContent = JSON.stringify({ agent_handoffs: data.agent_handoffs, policy_decision: data.policy_decision }, null, 2);
  document.querySelector("#output-json").textContent = JSON.stringify(output, null, 2); document.querySelector("#facts").textContent = JSON.stringify(data.facts, null, 2); result.classList.remove("hidden");
}
async function runCase() { const caseId = select.value; if (!caseId) return; status.textContent = `Đang chạy ${caseId}…`; status.classList.remove("error"); try { showCase(await request(`/api/cases/${caseId}`)); status.textContent = `${caseId} đã chạy và vượt qua verifier.`; } catch (error) { showError(error); } }
async function bootstrap() { try { const cases = await request("/api/cases"); select.innerHTML = cases.case_ids.map((id) => `<option value="${id}">${id}</option>`).join(""); const data = await request("/api/summary"); showSummary(data); status.textContent = "Sẵn sàng. Chọn một case để xem toàn bộ luồng agent."; await runCase(); } catch (error) { showError(error); } }
document.querySelector("#run-case").addEventListener("click", runCase);
document.querySelector("#run-all").addEventListener("click", async () => { status.textContent = "Đang quét 50 case…"; status.classList.remove("error"); try { const data = await request("/api/summary"); showSummary(data); status.textContent = `Đã quét ${data.total_cases} case thành công.`; } catch (error) { showError(error); } });
bootstrap();
