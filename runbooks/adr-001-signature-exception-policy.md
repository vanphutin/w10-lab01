# Architectural Decision Record (ADR)

## ADR 001: Signature Verification Exception Policy (Chính sách Ngoại lệ Xác thực Chữ ký)

- **Trạng thái (Status):** ĐÃ DUYỆT (ACCEPTED)
- **Tác giả (Author):** Van Phu Tin
- **Ngày (Date):** 2026-06-18

---

## 1. Bối Cảnh (Context)
Chúng ta đã tích hợp thành công **Sigstore Policy Controller** và cấu hình tài nguyên `ClusterImagePolicy` để đảm bảo các container image thuộc dự án (`ghcr.io/vanphutin/w10-api*`) bắt buộc phải có chữ ký số hợp lệ của doanh nghiệp mới được phép chạy trong cụm Kubernetes.

Tuy nhiên, nếu chúng ta áp dụng chính sách xác thực chữ ký này trên quy mô toàn cụm (Cluster-wide) cho mọi namespace, tất cả các ứng dụng bên thứ ba (Third-party) và hệ thống vận hành (System operators) sẽ bị chặn ngay lập tức do chúng không được ký bằng khóa riêng của chúng ta. Các hệ thống bị ảnh hưởng bao gồm:
- **Kubernetes System**: `kube-system` (kube-proxy, CoreDNS...)
- **GitOps Tooling**: `argocd`
- **Security & Policy**: `gatekeeper-system`
- **Secrets Management**: `external-secrets`
- **Monitoring**: `prometheus` / `kube-prometheus-stack`

Do đó, chúng ta cần một cơ chế để tạo ra **Chính sách Ngoại lệ (Exception Policy)**, phân tách rõ ràng giữa ứng dụng nội bộ cần bảo mật cao và các công cụ hệ thống chuẩn.

---

## 2. Quyết Định (Decision)
Chúng ta quyết định thực hiện chiến lược **Opt-In (Kích hoạt theo lựa chọn)** dựa trên nhãn Namespace (Namespace Labeling):

1. **Cấu hình Webhook của Sigstore Policy Controller**:
   Chỉ kiểm soát và xác thực chữ ký ảnh trên các namespace có gắn nhãn sau:
   ```yaml
   policy.sigstore.dev/include: "true"
   ```
2. **Phạm vi áp dụng**:
   - Gắn nhãn `policy.sigstore.dev/include=true` cho namespace **`demo`** (nơi ứng dụng API chạy) để áp dụng chính sách kiểm duyệt nghiêm ngặt.
   - Các namespace hệ thống như `kube-system`, `argocd`, `gatekeeper`, `external-secrets`, và `cosign-system` sẽ **KHÔNG** gắn nhãn này và được tự động miễn trừ khỏi quy trình xác thực chữ ký.
3. **Quản lý Rule trong ClusterImagePolicy**:
   - Chỉ áp dụng quy tắc khớp ảnh `glob: "ghcr.io/vanphutin/w10-api*"` để tập trung kiểm tra đúng phạm vi sản phẩm của doanh nghiệp, tránh gây nghẽn cho các ảnh công cộng như `nginx`, `redis` chạy ở các namespace khác.

---

## 3. Hệ Quả (Consequences)

### Hệ quả Tích cực (Positive):
* **Tính ổn định của hệ thống:** Các SRE/Ops có thể thoải mái cập nhật, cài đặt các Helm Chart từ cộng đồng (ArgoCD, Prometheus, Gatekeeper...) mà không cần phải tải về, đẩy lên registry nội bộ rồi ký lại bằng khóa riêng.
* **Thời gian triển khai nhanh:** Giảm thiểu tối đa overhead vận hành khi cấu hình cụm mới.

### Hệ quả Tiêu cực / Rủi ro (Negative / Risks):
* **Lỗ hổng tại các Namespace miễn trừ:** Nếu kẻ tấn công chiếm quyền tạo Pod trong các namespace không được gắn nhãn (như `kube-system` hay `default`), chúng có thể chạy các ảnh độc hại không có chữ ký.

### Biện pháp Giảm thiểu Rủi ro (Mitigation):
* Áp dụng **RBAC** cực kỳ nghiêm ngặt: Chỉ Admin mới có quyền thao tác trên các namespace hệ thống. Các tài khoản nhà phát triển (như `alice`) chỉ có quyền thao tác giới hạn tại namespace `demo`.
* Sử dụng **OPA Gatekeeper Constraints** để cấm chạy các container privileged, bắt buộc khai báo resource limits, và chặn việc tạo pod tự do ngoài namespace được phân phối.
