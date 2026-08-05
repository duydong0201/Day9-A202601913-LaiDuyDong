# Hướng dẫn thực hiện — Multi-Agent E-commerce Dispute Resolution

## 1. Mục tiêu

Xử lý 50 yêu cầu hỗ trợ khách hàng (`EC_001` đến `EC_050`) trên dữ liệu Olist. Với mỗi case, hệ thống phải đối chiếu dữ liệu gốc, xác định vấn đề chính, nguyên nhân, bên chịu trách nhiệm, bằng chứng, khoản hoàn tiền và hành động xử lý.

Nguyên tắc quan trọng: chỉ sử dụng thông tin có thể kiểm chứng trực tiếp từ CSV. Không tự suy diễn refund ledger, transaction ID, tracking checkpoint theo item hoặc sự kiện giao sai/giao thiếu.

## 2. Chuẩn bị dữ liệu và cấu trúc dự án

1. Kiểm tra 9 CSV trong `data/` và hiểu các khóa join chính:
   - `orders.customer_id -> customers.customer_id`
   - `orders.order_id -> order_items`, `order_payments`, `order_reviews`
   - `order_items.product_id -> products.product_id`
   - `order_items.seller_id -> sellers.seller_id`
2. Đọc 50 JSON từ `input/`; truy vấn bằng `customer_request.claimed_order_id`.
3. Dùng kiểu số thập phân chính xác cho tiền; mọi kết quả tiền làm tròn 2 chữ số.
4. Khai báo rõ trong source và `metadata.json` model chạy cho agent, kích thước tham số, framework và runtime. Mỗi agent phải dùng model có kích thước không quá 10B parameters.
5. Đặt API key/secret trong `.env`, không commit file này.

## 3. Thiết kế các agent và handoff

| Agent | Nhiệm vụ | Bàn giao cho Coordinator |
| --- | --- | --- |
| Coordinator | Nhận case, điều phối và tạo kết quả cuối | Assessment/output hoàn chỉnh |
| Order & Seller | Kiểm tra order status, item, seller, shipping limit | Order facts, item/seller evidence |
| Payment | Tổng payment, đối soát với item + freight | Payment facts, reconciliation result |
| Delivery | So sánh delivered date, estimated date, shipping limit | Kết luận giao trễ và dấu hiệu trách nhiệm |
| Policy | Áp dụng `EC_POLICY_V1` theo thứ tự ưu tiên | Issue, root cause, refund, action |
| Verifier | Kiểm tra schema, evidence, tiền và giới hạn số lượng | Output hợp lệ hoặc lỗi cần sửa |

Các handoff phải là dữ liệu có cấu trúc và dựa trên CSV, không chỉ là lời mô tả tự do của agent.

## 4. Xây dựng facts cho mỗi case

1. Tìm một order theo `claimed_order_id`.
2. Lấy toàn bộ item của order; một order có thể có nhiều item và seller.
3. Lấy toàn bộ payment row; `payment_value` là giá trị mỗi dòng payment, không phải giá trị một installment.
4. Tính:
   - `item_total_brl = tổng price`
   - `freight_total_brl = tổng freight_value`
   - `payment_total_brl = tổng payment_value`
5. Lấy các mốc thời gian từ order và item:
   - `order_delivered_carrier_date`
   - `order_delivered_customer_date`
   - `order_estimated_delivery_date`
   - `shipping_limit_date`
6. So sánh trực tiếp timestamp trong CSV, không cần đổi múi giờ.

## 5. Áp dụng chính sách EC_POLICY_V1

Áp dụng theo đúng thứ tự sau:

| Issue | Điều kiện | Root cause | Responsible party | Refund | Action |
| --- | --- | --- | --- | ---: | --- |
| `canceled_order_paid` | `order_status = canceled` và tổng payment > 0 | `ORDER_CANCELED_AFTER_PAYMENT` | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `unavailable_order_paid` | `order_status = unavailable` và tổng payment > 0 | `ORDER_UNAVAILABLE_AFTER_PAYMENT` | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `late_delivery_seller` | Giao sau estimated date, carrier nhận hàng sau shipping limit | `SELLER_HANDOFF_AFTER_LIMIT` | `seller` / seller ID vi phạm | Tổng freight | `refund_freight` |
| `late_delivery_logistics` | Giao sau estimated date, carrier nhận không muộn hơn shipping limit | `CARRIER_DELIVERED_AFTER_ESTIMATE` | `logistics_provider` / `LOGISTICS_PROVIDER` | Tổng freight | `refund_freight` |
| `valid_split_payment` | Có từ 2 payment row; payment khớp item + freight trong sai số 0.10 BRL | `MULTIPLE_PAYMENTS_RECONCILED` | Không có | 0 | `explain_valid_split_payment` |
| `unsupported_late_claim` | Không giao muộn hơn estimated date và payment khớp | `DELIVERY_WITHIN_ESTIMATE` | Không có | 0 | `reject_late_refund` |

Với nhiều item, seller được xem là giao carrier trễ nếu `order_delivered_carrier_date > shipping_limit_date` của item thuộc seller đó. Bộ 50 case chính thức không có tình huống mơ hồ giữa nhiều seller.

## 6. Tạo evidence và output

Chỉ sử dụng evidence ID tồn tại và đúng một trong các format:

```text
order:<order_id>
item:<order_id>:<order_item_id>
payment:<order_id>:<payment_sequential>
seller:<seller_id>
policy:<root_cause_code>
```

Mỗi input tạo một file cùng tên trong `output/`, đúng schema yêu cầu. Kiểm tra các giới hạn:

- Tối đa 5 ID cho mỗi entity set.
- Tối đa 10 evidence IDs.
- Tối đa 3 root causes, 3 responsible parties và 5 actions.
- `confidence` thuộc đoạn `[0, 1]`.
- `case_status = action_required` khi có hoàn tiền; ngược lại là `no_action`.
- Nếu order không có item: `item_ids`, `seller_ids` rỗng và tổng item/freight là `0.0`.

## 7. Kiểm thử và kiểm chứng

1. Kiểm tra JSON input/output parse được.
2. Xác minh case ID, order/item/payment/seller ID đều tồn tại trong CSV.
3. Đối soát tổng tiền và số tiền hoàn với policy.
4. Kiểm tra rule precedence để case canceled/unavailable không bị kết luận sang rule khác.
5. Chạy batch đủ 50 case, ghi trace của lần chạy mới nhất vào `trace.jsonl` (không append các lần chạy cũ).
6. Rà soát rằng `output/` có chính xác 50 file từ `EC_001.json` đến `EC_050.json`.

## 8. Tài liệu và nộp bài

Trước khi nộp, repo phải có:

- `architecture.md`: sơ đồ agent, vai trò, quyền truy cập và luồng handoff.
- `individual_5SoCuoiMHV_HoVaTen.md`: báo cáo cá nhân đúng phần việc thực hiện.
- `trace.jsonl`: trace chạy thật mới nhất của 50 case.
- `metadata.json`: model, parameter size, framework và runtime.

Commit toàn bộ source lên repo trước. Sau đó nén **chỉ** thư mục `output/` thành ZIP; ZIP phải gồm đúng 50 JSON và không chứa source code, `.env`, log hay artifact khác.
