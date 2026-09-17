f = 'app/static/index.html'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

import re
# Find the second occurrence of <section class="card section-hidden" id="automation-calendar-section"> and remove it and everything up to its </section>
first_index = content.find('<section class="card section-hidden" id="automation-calendar-section">')
if first_index != -1:
    second_index = content.find('<section class="card section-hidden" id="automation-calendar-section">', first_index + 1)
    if second_index != -1:
        end_section = content.find('</section>', second_index)
        if end_section != -1:
            content = content[:second_index] + content[end_section + len('</section>'):]
            with open(f, 'w', encoding='utf-8') as file:
                file.write(content)
