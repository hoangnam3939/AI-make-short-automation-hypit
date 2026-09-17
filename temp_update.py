f = 'app/static/index.html'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

ui_calendar = """
  <section class="card section-hidden" id="automation-calendar-section">
    <h2>Lập thực đơn tháng (Automation)</h2>
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <div>
        <label>Chiến lược:</label>
        <textarea id="calendar-strategy" placeholder="VD: Làm 90 video ngắn..." style="width: 100%; height: 80px;"></textarea>
      </div>
      <div>
        <label>Các nền tảng (cách nhau bởi dấu phẩy):</label>
        <input type="text" id="calendar-platforms" value="tiktok, facebook, youtube" style="width: 100%;">
      </div>
      <div style="display: flex; gap: 12px;">
        <div>
          <label>Số video/ngày:</label>
          <input type="number" id="calendar-videos-per-day" value="3" style="width: 100%;">
        </div>
        <div>
          <label>Số ngày:</label>
          <input type="number" id="calendar-days" value="30" style="width: 100%;">
        </div>
        <div>
          <label>Thời lượng (giây):</label>
          <input type="number" id="calendar-duration" value="24" style="width: 100%;">
        </div>
      </div>
      <button class="btn-primary" id="generate-calendar-btn" type="button">Lập thực đơn</button>
      <div id="calendar-results" style="margin-top: 16px;"></div>
    </div>
  </section>
"""

if 'id="automation-calendar-section"' not in content:
    content = content.replace('</section>\n\n  <section class="card">', '</section>\n' + ui_calendar + '\n  <section class="card">', 1)
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

f_js = 'app/static/app.js'
with open(f_js, 'r', encoding='utf-8') as file:
    content_js = file.read()

js_calendar = """
document.querySelectorAll('#pipeline-mode-choice input[name="pipeline-mode"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    const isAuto = e.target.value === "auto";
    const calSection = document.getElementById("automation-calendar-section");
    if(calSection) {
      calSection.classList.toggle("section-hidden", !isAuto);
    }
  });
});

const genCalBtn = document.getElementById("generate-calendar-btn");
if (genCalBtn) {
  genCalBtn.addEventListener("click", async () => {
    const strategy = document.getElementById("calendar-strategy").value.trim();
    const platforms = document.getElementById("calendar-platforms").value.split(",").map(s => s.trim()).filter(Boolean);
    const videos_per_day = parseInt(document.getElementById("calendar-videos-per-day").value, 10);
    const days = parseInt(document.getElementById("calendar-days").value, 10);
    const duration_seconds = parseInt(document.getElementById("calendar-duration").value, 10);

    if (!strategy || !platforms.length) return alert("Vui lòng nhập chiến lược và nền tảng");

    genCalBtn.disabled = true;
    genCalBtn.textContent = "Đang lập thực đơn...";
    
    try {
      const res = await fetch("/api/calendar/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy, platforms, videos_per_day, days, duration_seconds })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi API");
      
      let html = `<p><strong>Tổng số video:</strong> ` + data.total_videos + `</p>`;
      html += `<div style="max-height: 400px; overflow-y: auto;"><table style="width:100%; border-collapse: collapse;" border="1">`;
      html += `<tr><th>Ngày</th><th>Giờ</th><th>Nền tảng</th><th>Chủ đề</th><th>Hook</th></tr>`;
      data.slots.forEach(s => {
        html += `<tr><td>`+s.day+`</td><td>`+s.publish_time+`</td><td>`+s.platform+`</td><td>`+s.topic+`</td><td>`+s.hook_idea+`</td></tr>`;
      });
      html += `</table></div>`;
      document.getElementById("calendar-results").innerHTML = html;
    } catch(err) {
      alert(err.message);
    } finally {
      genCalBtn.disabled = false;
      genCalBtn.textContent = "Lập thực đơn";
    }
  });
}
"""

if 'id="automation-calendar-section"' not in content_js:
    with open(f_js, 'w', encoding='utf-8') as file:
        file.write(content_js + '\n' + js_calendar)

