# Hướng dẫn và Bản quyền Phần mềm Bên Thứ Ba (Third-Party Notices)

Dự án này có sử dụng hoặc tham khảo mã nguồn từ các dự án mã nguồn mở khác. Dưới đây là thông tin ghi công và giấy phép liên quan:

## 1. Watch-cli (@sonpiaz/watch-cli-mcp)
- **Tác giả:** Son Piaz (GitHub: @sonpiaz)
- **Giấy phép:** MIT License
- **Mục đích sử dụng:** Được tích hợp vào Agent 1 (và cả trợ lý Antigravity CLI) để đóng vai trò là đôi "Mắt" và "Tai". Công cụ này tự động tải video từ các nguồn mạng xã hội, trích xuất khung hình (keyframes) và phụ đề để cung cấp Context cho các Multimodal LLM (Claude 3.5 Sonnet, GPT-4o, v.v.) phân tích công thức Viral một cách chính xác nhất.

```text
MIT License

Copyright (c) Son Piaz (https://github.com/sonpiaz)

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
```

## 2. Hypit (hypit-ai/hypit)
- **Tác giả:** Hypit AI (GitHub: hypit-ai)
- **Giấy phép:** Modified Apache License 2.0 (Có điều kiện thương mại)
- **Mục đích sử dụng:** Sử dụng công nghệ SVML (Speech Video Markup Language) để làm công cụ nội bộ sản xuất video tự động dựa trên lời thoại (không cung cấp dịch vụ Multi-tenant SaaS ra bên ngoài).

```text
# Open Source License

Hypit is licensed under a modified version of the Apache License 2.0, with the following additional conditions:

1. Hypit may be utilized commercially for your own organization's purposes, including as a rendering or generation backend for applications your organization operates for itself, and as internal tooling within an enterprise. Should any of the conditions below be met, a commercial license must be obtained from the producer:

a. Multi-tenant service: Unless explicitly granted permission, you may not use Hypit to host a service where external users can log in and generate their own videos or workflows (SaaS).

(Original Apache 2.0 terms apply to all other usage).
```
