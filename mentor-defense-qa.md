# BỘ CÂU HỎI VẤN ĐÁP BẢO VỆ DỰ ÁN (MENTOR DEFENSE Q&A)
## CHỦ ĐỀ: KUBERNETES GITOPS, CANARY ANALYSIS, SECRET MANAGEMENT & SECURITY (WEEK 10)

Tài liệu này tổng hợp các câu hỏi "hóc búa" nhất mà Mentor có thể đặt ra khi chấm bài hoặc phỏng vấn để kiểm tra xem bạn thực sự hiểu sâu hệ thống hay chỉ đơn thuần là sao chép code. Các câu hỏi được chia theo nhóm thành phần công nghệ trong dự án.

---

## PHẦN 1: GITOPS & ARGOCD (APP OF APPS & SYNC WAVES)

### Q1: Mô hình "App of Apps" hoạt động như thế nào? Tại sao lại chọn mô hình này thay vì deploy lẻ tẻ từng Application?
*   **Trả lời bảo vệ:**
    *   **Cơ chế hoạt động:** Mô hình App of Apps sử dụng một ứng dụng gốc (Root Application - `root.yaml`) trỏ đến thư mục Git chứa các file cấu hình ứng dụng con (`argocd/apps`). Khi Root App đồng bộ, nó sẽ tự động quét thư mục đó và sinh ra các đối tượng `Application` con đại diện cho các thành phần (monitoring, api, rbac, gatekeeper...).
    *   **Lý do chọn:** 
        *   *Quản lý tập trung:* Chỉ cần apply duy nhất 1 file `root.yaml` lên cụm, toàn bộ hệ thống sẽ tự động được khởi tạo theo cấu trúc cây (Tree structure).
        *   *Tự động hóa hoàn toàn:* Tránh việc phải chạy thủ công lệnh `kubectl apply` cho từng ứng dụng con. Khi thêm một ứng dụng mới, chỉ cần đẩy file YAML của app đó vào thư mục `argocd/apps` trên Git, ArgoCD tự phát hiện và cài đặt.

### Q2: Em dựa vào tiêu chuẩn nào để phân chia giá trị `sync-wave` từ -2 đến 4 cho các ứng dụng? Điều gì xảy ra nếu tất cả các app đều có cùng sync-wave?
*   **Trả lời bảo vệ:**
    *   **Tiêu chuẩn phân chia:** Dựa trên **mối quan hệ phụ thuộc** của các tài nguyên.
        *   *Wave âm (-2, -1):* Dành cho các thành phần cốt lõi, nền tảng (Namespace, Operators/Controllers như Gatekeeper, ESO). Chúng định nghĩa các Custom Resource Definition (CRD) và Admission Webhook.
        *   *Wave trung bình (0, 1):* Dành cho hệ thống giám sát (Prometheus, Argo Rollouts) và phân quyền (RBAC), luật cảnh báo (Alerts).
        *   *Wave dương (2, 3, 4):* Dành cho ứng dụng chính (API Rollout) và các cấu hình lấy Secret/Chính sách bảo mật (Constraint, SecretStore, ClusterImagePolicy) vì chúng phụ thuộc vào việc Operator và Namespace đã chạy ổn định.
    *   **Nếu cùng sync-wave:** ArgoCD sẽ cố gắng deploy tất cả tài nguyên song song cùng một lúc. Điều này sẽ dẫn đến **lỗi đồng bộ (CRD not found)**. Ví dụ: K8s API Server sẽ từ chối tạo `SecretStore` vì External Secrets Operator chưa kịp cài xong để định nghĩa loại tài nguyên này.

---

## PHẦN 2: PROGRESSIVE DELIVERY (ARGO ROLLOUTS & CANARY ANALYSIS)

### Q3: So sánh sự khác nhau giữa tài nguyên `Deployment` mặc định và `Rollout` của Argo Rollouts? Tại sao chúng ta lại cần dùng `Rollout`?
*   **Trả lời bảo vệ:**
    *   `Deployment` mặc định chỉ hỗ trợ `RollingUpdate` (thay thế Pod cũ bằng Pod mới theo số lượng) và không hỗ trợ điều tiết traffic theo tỷ lệ % chính xác (ví dụ: chỉ cho 20% traffic qua bản mới). Nó cũng không tự tích hợp được với Prometheus để phân tích chỉ số lỗi và tự động rollback.
    *   `Rollout` là một Custom Resource cung cấp khả năng triển khai tịnh tiến (Canary) hoặc song song (Blue-Green). Nó cho phép chia luồng traffic chính xác qua Ingress/Service Mesh và tự động chạy phân tích metrics để đưa ra quyết định tiếp tục cập nhật (Promote) hoặc quay xe về bản cũ (Rollback) mà không cần con người can thiệp.

### Q4: Làm thế nào để Argo Rollouts biết được phiên bản mới (Canary) đang chạy bị lỗi để tự động rollback? Giải thích logic PromQL trong `AnalysisTemplate`?
*   **Trả lời bảo vệ:**
    *   Argo Rollouts làm việc này thông qua **`AnalysisTemplate`** kết hợp với **Prometheus**.
    *   Trong quá trình chạy Canary, Rollout Controller sẽ định kỳ gửi truy vấn PromQL đến Prometheus Server.
    *   **Logic PromQL sử dụng:**
        ```promql
        sum(rate(flask_http_request_duration_seconds_count{status=~"2..", route="/"}[2m])) 
        / 
        sum(rate(flask_http_request_duration_seconds_count{route="/"}[2m]))
        ```
        *Ý nghĩa:* Tính toán tỷ lệ thành công của HTTP request (các request có mã phản hồi `2xx` chia cho tổng số request) trong vòng 2 phút gần nhất.
    *   Nếu tỷ lệ này trả về kết quả **< 90%** (tương đương `success-condition: result[0] >= 0.9` bị vi phạm), đợt phân tích sẽ đánh dấu là Thất bại (Failure). Khi số lần thất bại vượt quá giới hạn (`failureLimit: 1`), Argo Rollout sẽ lập tức hạ luồng traffic về 0% ở bản mới và khôi phục 100% traffic về bản cũ.

---

## PHẦN 3: AN NINH & BẢO MẬT (OPA GATEKEEPER & SIGSTORE COSIGN)

### Q5: Tại sao em phải tách biệt `ConstraintTemplate` và `Constraint` trong OPA Gatekeeper? Lợi ích thiết kế này là gì?
*   **Trả lời bảo vệ:**
    *   **Tách biệt thiết kế:** 
        *   `ConstraintTemplate` đóng vai trò định nghĩa **mã nguồn logic kiểm tra** (viết bằng Rego) và cấu trúc tham số (Schema). Nó giống như một "Lớp" (Class) trong lập trình.
        *   `Constraint` đóng vai trò là **thực thể áp dụng** cụ thể. Nó sử dụng cấu trúc của Template, điền tham số thực tế (ví dụ: `maxReplicas: 5`) và khoanh vùng đối tượng áp dụng (ví dụ: áp dụng lên Deployment của namespace `demo`).
    *   **Lợi ích:** Tái sử dụng mã nguồn. Người viết code Rego (thường là đội Bảo mật/SecOps) chỉ cần viết Template một lần. Đội vận hành (DevOps/SRE) có thể tạo ra hàng chục luật Constraint khác nhau cho các môi trường khác nhau (Dev tối đa 2 replicas, Prod tối đa 10 replicas) chỉ bằng việc khai báo tham số đơn giản mà không cần chạm vào Rego code.

### Q6: Trình bày quy trình hoạt động của Sigstore Policy Controller và Cosign trong cụm? Nó bảo vệ cụm khỏi những nguy cơ gì?
*   **Trả lời bảo vệ:**
    *   **Quy trình hoạt động:** 
        1.  Trong pipeline CI/CD (GitHub Actions), sau khi build Docker image, ta dùng công cụ `Cosign` để ký số (Sign) lên image bằng cặp khóa bảo mật (Private Key). Chữ ký này được đẩy lên registry.
        2.  Trong cụm K8s, ta deploy `Sigstore Policy Controller` đóng vai trò là một **Mutating/Validating Admission Webhook**.
        3.  Ta áp dụng **`ClusterImagePolicy`** chứa khóa công khai (Public Key).
        4.  Khi có yêu cầu chạy một Pod mới, API Server gửi thông tin image đến Policy Controller. Controller này tìm chữ ký của image trên Registry và đối chiếu với Public Key.
        5.  Nếu chữ ký khớp và hợp lệ, Pod được phép chạy. Nếu không khớp hoặc không có chữ ký, yêu cầu deploy bị chặn đứng hoàn toàn.
    *   **Nguy cơ ngăn chặn:** Ngăn ngừa kẻ tấn công giả mạo Docker registry, tấn công chuỗi cung ứng (Supply Chain Attack) bằng cách chèn container image độc hại vào cụm.

---

## PHẦN 4: QUẢN LÝ THÔNG TIN BÍ MẬT (EXTERNAL SECRETS OPERATOR)

### Q7: Tại sao lại chọn External Secrets Operator (ESO) thay vì sử dụng Kubernetes Secret mặc định hay lưu Secret base64 trên Git?
*   **Trả lời bảo vệ:**
    *   **Hạn chế của K8s Secret & Git:**
        *   Secret base64 trên Git thực chất chỉ là mã hóa văn bản thuần, bất kỳ ai có quyền đọc Git đều có thể giải mã dễ dàng (rò rỉ thông tin bí mật).
        *   Kubernetes Secret mặc định được lưu trữ dưới dạng plain text trong database `etcd` của cụm, không tự động xoay vòng (rotation) và khó quản lý tập trung nếu có nhiều cụm.
    *   **Giải pháp ESO:** ESO đóng vai trò là cầu nối. Nó kéo Secret từ các nguồn lưu trữ chuyên dụng an toàn bên ngoài (ở đây là **AWS Secrets Manager**) về cụm một cách tự động. Mật khẩu thực tế chỉ nằm trên AWS Secrets Manager, trên Git chỉ lưu file cấu hình tham chiếu (`ExternalSecret`). Hệ thống tự động đồng bộ định kỳ (ví dụ: mỗi 10 giây), nếu mật khẩu trên AWS thay đổi, cụm K8s tự động cập nhật theo mà không cần cấu hình thủ công.

### Q8: Sự khác nhau giữa `SecretStore` và `ClusterSecretStore` trong cấu hình ESO là gì? Dự án này đang dùng loại nào và tại sao?
*   **Trả lời bảo vệ:**
    *   **Phân biệt:**
        *   `SecretStore` là tài nguyên **Namespace-scoped**. Nó chỉ có thể kết nối và phục vụ việc tạo Secret trong cùng namespace chứa nó.
        *   `ClusterSecretStore` là tài nguyên **Cluster-wide**. Nó được khai báo một lần cấp toàn cụm và tất cả các namespace khác đều có thể sử dụng chung để tạo Secret.
    *   **Dự án đang dùng:** Dự án của chúng ta đang sử dụng **`SecretStore`** (đặt trong namespace `demo`).
    *   **Lý do chọn:** Đảm bảo nguyên tắc bảo mật tối thiểu (Least Privilege). Ta chỉ muốn ứng dụng trong namespace `demo` được phép kết nối với AWS Secrets Manager để lấy database secret của chính nó. Việc giới hạn bằng `SecretStore` ngăn chặn các Pod ở namespace khác (ví dụ: dev, testing) lợi dụng cấu hình này để lấy trộm mật khẩu.

---

## PHẦN 5: OBSERVABILITY & SRE (PROMETHEUS, SERVICEMONITOR & ALERTS)

### Q9: Sự khác biệt giữa các chỉ số kiểm tra lỗi trong Canary Analysis (Argo Rollouts) và PrometheusRule (Alertmanager) là gì? Tại sao ngưỡng (threshold) của chúng lại khác nhau?
*   **Trả lời bảo vệ:**
    *   **Mục đích khác nhau:**
        *   *Canary Analysis (Ngưỡng 90%):* Dùng để **phản ứng tức thời** trong quá trình deploy phiên bản mới. Nếu bản mới chạy thử nghiệm phát sinh lỗi quá 10%, hệ thống tự động rollback ngay để tránh ảnh hưởng diện rộng.
        *   *PrometheusRule (Ngưỡng 95%):* Dùng để **giám sát chất lượng dịch vụ dài hạn (SLO)** của toàn bộ hệ thống (cả bản cũ lẫn bản mới). Nếu tỷ lệ thành công tổng thể tụt dưới 95%, nó đại diện cho một sự cố nghiêm trọng đang xảy ra trên diện rộng và cần báo động (bắn email/alert) để kỹ sư SRE vào cuộc debug.
    *   **Ngưỡng khác nhau:** Ngưỡng Canary (90%) thấp hơn vì bản Canary chỉ nhận lượng traffic nhỏ (ví dụ: 20%), tỷ lệ lỗi đột biến của nó dễ tăng cao trong thời gian ngắn do số lượng mẫu request ít. Ngưỡng SLO hệ thống (95%) cao hơn vì nó đại diện cho trải nghiệm của toàn bộ người dùng cuối.

### Q10: Nếu ứng dụng Flask API của em phát sinh lỗi, làm cách nào Alertmanager có thể gửi email cho em? Hãy giải thích luồng đi của một Alert.
*   **Trả lời bảo vệ:**
    1.  Ứng dụng Flask API phát sinh lỗi, metrics tỷ lệ thành công giảm xuống dưới 95%.
    2.  **Prometheus Server** liên tục chạy câu lệnh rule check được định nghĩa trong `PrometheusRule`. Phát hiện điều kiện vi phạm kéo dài quá thời gian quy định (ví dụ: `for: 30s`), Prometheus chuyển trạng thái cảnh báo thành `Firing`.
    3.  Prometheus Server gửi thông tin cảnh báo (Alert payload) sang **Alertmanager**.
    4.  Alertmanager tiếp nhận, thực hiện gom nhóm (Grouping) các cảnh báo trùng, đợi trong 10 giây (`group_wait: 10s`) để gộp chung email.
    5.  Nó định tuyến cảnh báo đến receiver `email-notifications` dựa trên nhãn của alert.
    6.  Alertmanager sử dụng thông tin SMTP cấu hình trong `smarthost: smtp.gmail.com:587` và thông tin xác thực chứa trong file secret (`auth_password_file`) để thiết lập kết nối an toàn (TLS) và gửi email chứa template HTML trực quan đến địa chỉ `vanphutin2902@gmail.com`.

---

## PHẦN 6: CÁC TÌNH HUỐNG NÂNG CAO & KHẮC PHỤC SỰ CỐ (ADVANCED SCENARIOS & TROUBLESHOOTING)

### Q11: Trong Progressive Delivery, nếu Prometheus Server bị sập (down) hoặc bị mất kết nối mạng ngay giữa quá trình chạy Canary Analysis, Argo Rollout sẽ xử lý như thế nào? Nó sẽ tự động Rollback hay tự động Promote? Làm sao để cấu hình hành vi này?
*   **Trả lời bảo vệ:**
    *   **Hành vi mặc định:** Khi Prometheus bị sập, Argo Rollouts sẽ nhận lỗi kết nối (HTTP connection error hoặc empty response) khi truy vấn metrics. Theo mặc định, Rollout Controller sẽ coi đây là trạng thái lỗi đo lường (`Error` hoặc `Inconclusive`) chứ không phải là lỗi logic ứng dụng (`Failure`). Nó có thể tạm dừng (Pause) hoặc tiếp tục thử lại dựa trên cấu hình mà không tự động rollback ngay lập tức.
    *   **Cách cấu hình an toàn (Fail-Secure):**
        *   Sử dụng tham số `consecutiveErrorLimit` hoặc `failureLimit` trong `AnalysisTemplate` để giới hạn số lần lỗi kết nối liên tiếp tối đa cho phép.
        *   Nếu số lần truy vấn lỗi vượt quá giới hạn này, trạng thái của `AnalysisRun` sẽ tự động chuyển từ `Error` sang `Failed`. Khi đó, Argo Rollouts lập tức kích hoạt quy trình **auto rollback** khôi phục phiên bản cũ để đảm bảo an toàn cho cụm.

### Q12: OPA Gatekeeper có chế độ Admission Webhook. Nếu Gatekeeper Pod bị sập (ví dụ: bị OOMKilled hoặc nút chứa nó bị lỗi), các yêu cầu `kubectl apply` hoặc deploy từ ArgoCD của chúng ta có bị chặn lại không? Làm thế nào để điều chỉnh hành vi này?
*   **Trả lời bảo vệ:**
    *   **Cơ chế hoạt động:** Hành vi này phụ thuộc hoàn toàn vào thuộc tính `failurePolicy` (được cấu hình là `Fail` hoặc `Ignore`) trong tài nguyên `ValidatingWebhookConfiguration` của Gatekeeper đăng ký với K8s API Server.
    *   **Chi tiết hai cấu hình:**
        *   `failurePolicy: Fail` (Chế độ mặc định an toàn): Nếu Gatekeeper Webhook không phản hồi hoặc bị sập, API Server sẽ **từ chối tất cả các yêu cầu thay đổi tài nguyên** (create/update) thuộc phạm vi của webhook. Điều này đảm bảo an toàn tuyệt đối (không manifest độc hại nào lọt vào cụm khi Gatekeeper offline), nhưng có nhược điểm là làm tê liệt khả năng deploy của cả cụm (kể cả ArgoCD cũng không thể sync được).
        - `failurePolicy: Ignore`: API Server sẽ bỏ qua Gatekeeper và cho phép các yêu cầu đi qua bình thường nếu Gatekeeper bị sập. Chế độ này giữ cho cụm hoạt động liên tục (HA), nhưng tạo ra rủi ro bảo mật lớn vì các cấu hình thiếu an toàn có thể bị lọt vào cụm trong thời gian Gatekeeper offline.

### Q13: Trong quy trình Ký ảnh bằng Cosign, tại sao dự án của chúng ta lại lưu khóa công khai `cosign.pub` trực tiếp trên Git để cấu hình `ClusterImagePolicy`, trong khi khóa bí mật lại phải lưu trong GitHub Secrets? Có giải pháp nào giúp ký ảnh và xác thực mà không cần quản lý cặp khóa (Keyless Signing) không?
*   **Trả lời bảo vệ:**
    *   **Về khóa công khai:** Khóa công khai (`cosign.pub`) chỉ dùng để xác minh chữ ký (đối chiếu toán học). Nó không thể dùng để ký giả mạo image. Do đó, việc lưu nó công khai trên Git là hoàn toàn an toàn và cần thiết để GitOps (ArgoCD) có thể tự động đồng bộ chính sách `ClusterImagePolicy` xuống cụm mà không cần can thiệp thủ công.
    *   **Giải pháp Keyless Signing (Ký không dùng khóa):**
        *   *Cơ chế:* Sử dụng **Sigstore Fulcio** (Certificate Authority) và **Sigstore Rekor** (Transparency Log) kết hợp với OIDC (OpenID Connect) từ GitHub Actions.
        *   *Luồng chạy:* GitHub Actions nhận diện môi trường chạy hợp lệ thông qua OIDC Token do GitHub cung cấp. Cosign gửi token này lên Fulcio để xin một chứng chỉ số ngắn hạn (chỉ có hiệu lực trong 10 phút) gắn liền với danh tính GitHub Action đó, dùng chứng chỉ này ký image và ghi log lại trên Rekor.
        *   *Lợi ích:* Loại bỏ hoàn toàn việc tạo, lưu trữ hay xoay vòng khóa bí mật trên GitHub Secrets, loại bỏ hoàn toàn nguy cơ rò rỉ private key.

### Q14: Khi ESO đồng bộ Secret mới từ AWS Secrets Manager vào Kubernetes Secret thành công, làm sao ứng dụng Flask API của chúng ta phát hiện và cập nhật giá trị mới này mà không bị khởi động lại? Giải thích cơ chế lập trình phía ứng dụng (Application Side Logic).
*   **Trả lời bảo vệ:**
    *   **Cơ chế mount volume của K8s:** Khi K8s Secret được mount vào Pod dưới dạng file trong thư mục `/etc/secrets/`, kubelet sẽ đồng bộ hóa (symlink update) nội dung file này khi Secret trên cụm thay đổi. Thời gian trễ tùy thuộc vào cấu hình `syncFrequency` và `maxSyncPeriod` của kubelet (thường từ 10 đến 60 giây).
    *   **Cơ chế đọc file phía ứng dụng:**
        *   Ứng dụng Flask API của chúng ta **không lưu cache** giá trị mật khẩu vào biến toàn cục khi khởi động.
        *   Thay vào đó, trong code Flask API, mỗi lần xử lý một HTTP request cần đến Secret (ví dụ: kết nối Database), ứng dụng sẽ thực hiện **đọc trực tiếp từ file** `/etc/secrets/db-password`:
          ```python
          def get_db_connection():
              with open("/etc/secrets/db-password", "r") as f:
                  password = f.read().strip()
              # Kết nối Database với password mới nhất
          ```
        *   Điều này giúp ứng dụng luôn đọc được giá trị mới nhất ngay khi file được kubelet cập nhật, duy trì hoạt động liên tục với số lần restart của Pod bằng 0.

### Q15: Làm sao để ngăn chặn tình trạng "Tấn công vòng lặp đồng bộ" (Sync Loop / Sync Storm) giữa ArgoCD và External Secrets Operator (ESO) nếu một bên cố gắng sửa K8s Secret và bên kia ghi đè lại?
*   **Trả lời bảo vệ:**
    *   **Cơ chế phòng tránh:** ArgoCD mặc định sẽ cố gắng đưa trạng thái của cụm về đúng như khai báo trên Git. Nếu ta khai báo K8s Secret trên Git và apply, ArgoCD sẽ quản lý nó. Khi ESO cập nhật giá trị mới của Secret từ AWS Secrets Manager xuống cụm, ArgoCD sẽ phát hiện ra sự khác biệt (Out-of-Sync) và ghi đè lại giá trị cũ trên Git, tạo ra một vòng lặp đồng bộ vô hạn (Sync Storm) gây tốn tài nguyên và lỗi kết nối.
    *   **Cách giải quyết triệt để:**
        1.  **Không khai báo Kubernetes Secret thực tế trên Git**: Ta chỉ khai báo tài nguyên `ExternalSecret` trên Git. ArgoCD chỉ quản lý `ExternalSecret`. Khi apply, ESO controller tự động tạo ra và cập nhật K8s Secret thực tế. Vì K8s Secret này không được khai báo trong Git, ArgoCD sẽ bỏ qua và không kiểm soát nó.
        2.  **Sử dụng annotation bỏ qua giám sát của ArgoCD**: Nếu bắt buộc phải khai báo khung Secret trên Git, ta cần thêm annotation `argocd.argoproj.io/compare-options: IgnoreExtraneous` hoặc cấu hình `ignoreDifferences` trong Application của ArgoCD để bảo nó bỏ qua việc so sánh các trường dữ liệu (`data`) của Secret đó.

---

## PHẦN 7: CÂU HỎI XOÁY TRỰC TIẾP VÀO CẤU HÌNH & CODE (CODE-SPECIFIC MANIFEST QUESTIONS)

### Q16: Nhìn vào workflow `.github/workflows/build-push.yml`, tại sao bạn phải build Docker image 2 lần (lần 1 ở line 58-63 với tag `:local-scan`, lần 2 ở line 75-82)? Tại sao Trivy action cần cấu hình `exit-code: '1'`?
*   **Trả lời bảo vệ:**
    *   **Lý do build 2 lần:**
        *   *Lần 1 (build local-scan):* Ta build image cục bộ trên runner của GitHub Actions và lưu tạm (`load: true`). Mục đích là để cấp cho **Trivy** thực hiện quét lỗ hổng bảo mật trực tiếp trên runner trước khi đẩy lên Registry công khai.
        *   *Lần 2 (build and push):* Sau khi Trivy xác nhận image an toàn (không có lỗi bảo mật nghiêm trọng), ta mới build lại và thực hiện đẩy lên GitHub Container Registry (`push: true`) với các tags chính thức (`latest`, `v*`, `sha-*`). Điều này đảm bảo không bao giờ đẩy một image có lỗ hổng bảo mật lên registry (Shift-Left Security).
    *   **Ý nghĩa của `exit-code: '1'`:** Mặc định, Trivy chỉ log lỗi ra terminal và trả về exit-code = 0 (tức là pipeline vẫn pass). Việc đặt `exit-code: '1'` bắt buộc GitHub Actions phải **dừng ngay lập tức (fail pipeline)** nếu Trivy phát hiện bất kỳ lỗ hổng nào thuộc mức `HIGH` hoặc `CRITICAL`. Nhờ đó, ngăn chặn hoàn toàn việc build và push ảnh không an toàn ở bước tiếp theo.

### Q17: Trong `rollout.yaml` line 58, biến môi trường `ERROR_RATE` có giá trị `0.15` (15%). Hãy cho biết cơ chế ứng dụng giả lập lỗi dựa trên biến này. Đồng thời, tại sao thuộc tính `startingStep: 1` lại được khai báo ở phần `analysis`? Bắt đầu chạy Analysis từ bước 1 (weight = 10%) có điểm lợi và hại gì?
*   **Trả lời bảo vệ:**
    *   **Cơ chế giả lập lỗi:** Trong code Flask API, khi nhận HTTP request, ứng dụng sẽ sinh ngẫu nhiên một số thực trong khoảng `[0, 1]`. Nếu số này nhỏ hơn giá trị của biến môi trường `ERROR_RATE` (0.15), ứng dụng sẽ tự động trả về lỗi HTTP 500 (Internal Server Error) để giả lập lỗi hệ thống.
    *   **Ý nghĩa của `startingStep: 1`:** Chỉ định Argo Rollouts bắt đầu chạy Analysis ngay từ bước đầu tiên của chiến lược Canary (khi lưu lượng traffic định tuyến sang bản mới chỉ ở mức 10%).
    *   **Điểm lợi:** Phản ứng cực nhanh. Nếu image mới bị lỗi nghiêm trọng (crash loop hoặc lỗi logic diện rộng), Analysis sẽ phát hiện ra ngay từ lúc 10% traffic và rollback lập tức, giúp bảo vệ 90% người dùng còn lại không bị ảnh hưởng.
    *   **Điểm hại (Rủi ro):** Số lượng request đi vào bản mới lúc 10% traffic là rất nhỏ. Trong thống kê, số mẫu nhỏ (low sample size) dễ dẫn đến sai lệch lớn. Chỉ cần 1 hoặc 2 request lỗi vô tình cũng có thể làm tỉ lệ thành công tụt mạnh xuống dưới 90%, dẫn đến **báo động giả (False Positive)** và rollback nhầm một phiên bản hoàn toàn bình thường.

### Q18: Hãy giải thích cú pháp truy vấn PromQL trong `analysis-template.yaml` (line 39-44). Cụ thể hàm `scalar(...)` và nhãn `status!~"5.."` được sử dụng để làm gì? Điều gì xảy ra nếu hệ thống không nhận được request nào trong vòng 2 phút gần nhất (no traffic)?
*   **Trả lời bảo vệ:**
    *   **Giải thích PromQL:**
        *   `status!~"5.."`: Lọc bỏ toàn bộ các HTTP request có mã trạng thái bắt đầu bằng số 5 (tức lỗi server-side 5xx như 500, 503). Các request có status 2xx, 3xx hoặc 4xx vẫn được coi là thành công từ góc độ vận hành hạ tầng API.
        *   `scalar(...)`: Chuyển đổi kết quả của phép chia rate (vốn là một vector chứa 1 phần tử) thành một giá trị số thực đơn (scalar value). Argo Rollouts yêu cầu kết quả trả về phải là scalar thì mới thực hiện so sánh toán học `result >= 0.90` được.
    *   **Trường hợp No Traffic:**
        *   Nếu không có request nào, mẫu số sẽ bằng 0. Phép toán chia cho 0 trong Prometheus sẽ trả về kết quả rỗng (`no data`).
        *   Do kết quả trả về không phải là một số thực, điều kiện `successCondition` không thể đánh giá. Argo Rollouts sẽ coi đây là trạng thái lỗi kết quả (`Inconclusive` hoặc `Error`).
        *   *Cách khắc phục thực tế:* Ta nên bọc câu lệnh PromQL bằng hàm `or vector(1)` để trả về mặc định là 1 (100% thành công) khi không có traffic, tránh việc rollback nhầm khi hệ thống rảnh rỗi.

### Q19: Nhìn vào file `gatekeeper/constraints/k8s-max-replicas.yaml`, hãy giải thích đoạn Rego từ dòng 46-55. Làm thế nào Gatekeeper trích xuất số replica của resource gửi lên và đối chiếu với Constraint? Nhãn `match.kinds` ở dòng 71-73 đóng vai trò gì?
*   **Trả lời bảo vệ:**
    *   **Giải thích Rego (line 46-55):**
        *   `replicas := input.review.object.spec.replicas`: `input.review.object` chứa toàn bộ nội dung manifest YAML của resource đang được gửi lên API Server (Admission Review Request). Dòng này trích xuất trường `replicas` từ spec của Deployment.
        *   `max_replicas := input.parameters.maxReplicas`: Trích xuất giá trị tham số cấu hình trong file Constraint bên dưới (giá trị là 5).
        *   `replicas > max_replicas`: Biểu thức so sánh điều kiện vi phạm. Nếu số replica thực tế lớn hơn max cho phép, block `violation` sẽ trả về `true` và chặn đứng request.
    *   **Vai trò của `match.kinds` (line 71-73):** Đây là bộ lọc phạm vi áp dụng (Targeting filter). Nó giới hạn chính sách này chỉ áp dụng cho tài nguyên có `kind: Deployment` thuộc apiGroups `apps`. Nếu không có bộ lọc này, Gatekeeper sẽ quét và báo lỗi trên mọi tài nguyên khác (như ReplicaSet, StatefulSet hoặc Pod) vốn không có trường `.spec.replicas` giống Deployment, gây ra lỗi logic trong hệ thống.

### Q20: Trong cấu hình `secret-store.yaml`, làm cách nào `SecretStore` kết nối được với AWS Secrets Manager? Nó sử dụng Kubernetes Secret nào và làm sao Secret đó được tạo ra? Trong `external-secret.yaml`, tham số `creationPolicy: Owner` có ý nghĩa như thế nào đối với vòng đời của Secret?
*   **Trả lời bảo vệ:**
    *   **Cơ chế kết nối:** `SecretStore` khai báo provider là `aws` ở khu vực `ap-southeast-1`. Nó sử dụng thông tin IAM credentials cấu hình tại `auth.secretRef` để xác thực với AWS API.
    *   **Kubernetes Secret sử dụng:** Nó tham chiếu đến Secret `awssm-secret` trong namespace `demo` (chứa 2 key: `access-key` và `secret-access-key`). Secret này được tạo ra thủ công dưới cụm thông qua lệnh chạy local (sử dụng AWS CLI của DevOps engineer để lấy credentials hiện tại và apply vào cụm qua pipe `kubectl create secret ...`), đảm bảo khóa bảo mật không bị lưu vết trên Git.
    *   **Ý nghĩa của `creationPolicy: Owner`:** Thiết lập mối quan hệ sở hữu (Owner Reference) trong Kubernetes giữa `ExternalSecret` (nguồn) và `api-db-secret` (đích). Nếu ta xóa tài nguyên `ExternalSecret` khỏi cụm, Kubernetes Garbage Collector sẽ tự động dọn dẹp và xóa bỏ hoàn toàn Kubernetes Secret tương ứng, tránh việc để lại các Secret mồ côi (orphaned secrets) gây rò rỉ thông tin hoặc khó quản trị.

### Q21: Hãy nhìn vào `roles.yaml` dòng 55, tại sao vai trò `sre` lại có quyền `verbs: ["get", "list", "watch", "create", "update", "patch", "delete", "escalate", "bind"]`? Quyền `escalate` và `bind` ở đây có rủi ro bảo mật gì không? Tại sao `developer-binding` cần chỉ định `namespace: demo` còn `sre-binding` thì không?
*   **Trả lời bảo vệ:**
    *   **Tại sao SRE cần `escalate` và `bind`:** SRE cần quyền vận hành và khắc phục sự cố hệ thống cấp cao. Quyền `bind` cho phép SRE tạo ra các `RoleBinding` để phân quyền cho các tài nguyên khác. Quyền `escalate` cho phép SRE chỉnh sửa hoặc tạo các Role có quyền cao hơn quyền hiện tại của chính họ mà không bị API Server chặn lại.
    *   **Rủi ro bảo mật:** Đây là hai quyền **cực kỳ nhạy cảm và nguy hiểm**. Nếu tài khoản của SRE bị hacker chiếm quyền, hacker có thể dùng `escalate` và `bind` để tự gán quyền `cluster-admin` (quyền tối cao) cho bản thân, vượt qua mọi rào cản bảo mật. Do đó, trong thực tế, chỉ những kỹ sư hệ thống cốt lõi mới được gán quyền này và phải được giám sát chặt chẽ qua Audit Logs.
    *   **Sự khác biệt về Namespace trong Binding:**
        *   `developer-binding` sử dụng tài nguyên **`RoleBinding`** gắn với namespace `demo`. Mục đích là giới hạn quyền hạn của Alice chỉ có hiệu lực bên trong namespace `demo`, cô ấy hoàn toàn không có quyền thao tác trên các namespace khác.
        *   `sre-binding` sử dụng tài nguyên **`ClusterRoleBinding`**. Tài nguyên này ở cấp độ Cluster-wide (không thuộc namespace nào), giúp tự động áp dụng các quyền trong `ClusterRole` của SRE (như xem nodes, quản lý pods) trên **tất cả các namespace** hiện có và sẽ có trong tương lai mà không cần viết nhiều file cấu hình nhỏ lẻ.

### Q22: Trong `cluster-image-policy.yaml`, tại sao chúng ta chỉ cấu hình áp dụng xác thực chữ ký cho pattern `glob: "ghcr.io/vanphutin/w10-api*"`? Nếu một Pod của ứng dụng bên thứ ba (như `postgres` hay `prometheus`) không có chữ ký số được cài vào cụm, nó có bị chặn lại không?
*   **Trả lời bảo vệ:**
    *   **Tại sao giới hạn glob:** Nhãn hiệu và hình ảnh ứng dụng của bên thứ ba (như các thư viện Prometheus, ArgoCD, Postgres...) được duy trì bởi cộng đồng quốc tế và họ không ký bằng khóa Cosign của riêng ta. Nếu ta áp dụng chính sách ký số cho toàn bộ cụm (`glob: "*"`), Sigstore Policy Controller sẽ chặn đứng toàn bộ các image hệ thống đó, khiến cụm Kubernetes bị tê liệt và không thể khởi động các dịch vụ nền.
    *   **Sự ảnh hưởng:** Vì ta cấu hình bộ lọc cụ thể (`glob: "ghcr.io/vanphutin/w10-api*"`), các Pod của bên thứ ba như `postgres` hay `prometheus` sẽ **không chịu ảnh hưởng** của chính sách này và vẫn khởi chạy bình thường mà không bị chặn lại. Chỉ những container sử dụng image API do chính ta phát triển mới bắt buộc phải đi qua quy trình xác thực chữ ký số Cosign.

### Q23: Trong file `k8s-no-latest-tag.yaml`, hãy giải thích cách Rego phát hiện được một container image không chỉ định tag (ví dụ: chỉ ghi `image: nginx`). Tại sao điều này lại bị đánh dấu là vi phạm?
*   **Trả lời bảo vệ:**
    *   **Cách Rego phát hiện:** Trong Rego, ta định nghĩa hàm:
        ```rego
        is_latest(image) {
          not contains(image, ":")
        }
        ```
        Nếu tên image khai báo trong Pod spec không chứa ký tự `:` (dấu hai chấm), hàm này sẽ trả về `true` (tức là vi phạm).
    *   **Lý do vi phạm:** Trong Kubernetes, nếu tên image không chứa dấu `:`, Kubernetes API Server sẽ mặc định hiểu là tag `:latest` và tự động thiết lập thuộc tính `imagePullPolicy: Always`. Việc không ghi rõ tag thực chất chính là đang chạy ảnh `latest` một cách gián tiếp, gây ra rủi ro bảo mật và mất tính nhất quán phiên bản. Vì vậy, ta bắt buộc phải bắt trường hợp này để chặn lại.

### Q24: Trong `k8s-require-resources.yaml`, tại sao chính sách Gatekeeper lại chỉ bắt buộc khai báo `limits` mà không bắt buộc khai báo `requests`? Nếu một container chỉ đặt limit cho Memory mà quên đặt limit CPU, nó có bị block không?
*   **Trả lời bảo vệ:**
    *   **Tại sao chỉ bắt buộc limits:**
        *   `requests` (yêu cầu tối thiểu) chủ yếu được Kubernetes Scheduler sử dụng để chọn Node phù hợp để đặt Pod. Nếu Pod thiếu request, nó vẫn chạy được bình thường.
        *   `limits` (giới hạn tối đa) là **chốt chặn an toàn**. Nếu thiếu limit, một container bị lỗi rò rỉ bộ nhớ (Memory Leak) có thể ngốn sạch dung lượng RAM của Node vật lý đó, làm chết các Pod quan trọng khác đang chạy chung Node (lỗi OOMKilled dây chuyền). Vì vậy, khía cạnh bảo an của Gatekeeper ưu tiên bắt buộc phải khai báo `limits`.
    *   **Khi thiếu CPU limit:** Sẽ bị **chặn lại ngay**. Trong code Rego của Template:
        ```rego
        has_limits(container) {
          container.resources.limits.cpu
          container.resources.limits.memory
        }
        ```
        Phép kiểm tra `not has_limits(container)` sẽ trả về `true` nếu thiếu **một trong hai** trường `limits.cpu` hoặc `limits.memory`. Điều này buộc lập trình viên phải khai báo đầy đủ cả hai giới hạn trần mới được deploy.

### Q25: Nhìn vào `servicemonitor.yaml` dòng 34, tại sao thuộc tính `port` lại được đặt là `http` (dạng chuỗi) thay vì ghi trực tiếp cổng số `8080`? Nếu sửa thành `port: 8080` thì hệ thống có cào được metrics không?
*   **Trả lời bảo vệ:**
    *   **Tại sao dùng tên cổng:** Prometheus Operator thiết kế trường `port` trong `ServiceMonitor` để đối chiếu với **tên định danh của cổng (Port Name)** được khai báo trong tài nguyên `Service` (`service.yaml`), chứ không phải số cổng trực tiếp.
    *   **Nếu sửa thành `port: 8080`:** Hệ thống sẽ **không cào được metrics**. Prometheus Operator sẽ báo lỗi cấu hình hoặc không thể phân giải endpoint, vì nó sẽ tìm kiếm một cổng có tên là `"8080"` trong Service mà không tìm thấy (ở Service ta chỉ khai báo `name: http` ứng với `port: 8080`).

### Q26: Hãy trình bày cấu trúc của tệp App of Apps gốc `argocd/root.yaml`. Làm thế nào nó có thể tự nhận biết và sync toàn bộ các app con trong thư mục `argocd/apps`?
*   **Trả lời bảo vệ:**
    *   Tệp `root.yaml` định nghĩa một tài nguyên `Application` có tên là `root-app` trong namespace `argocd`.
    *   **Điểm mấu chốt nằm ở phần `spec`:**
        *   `source.path` được chỉ định là `argocd/apps` (trỏ đến thư mục chứa 13 file YAML của các ứng dụng con trong repo Git).
        *   `destination.namespace` đặt là `argocd` (vì các tài nguyên Application con cần phải được tạo ở namespace chứa bộ não ArgoCD để nó quản lý).
    *   Khi `root-app` được đồng bộ, ArgoCD sẽ đọc toàn bộ các file manifest chứa trong thư mục `argocd/apps` trên Git và tạo chúng ra dưới cụm. Từ đó, mỗi file YAML con lại đóng vai trò là một Application độc lập tự đồng bộ mã nguồn của từng thành phần tương ứng. Cấu trúc này tạo thành một mô hình quản lý dạng cây cực kỳ khoa học.

