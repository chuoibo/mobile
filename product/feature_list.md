# RỦ ĐI — AI-FIRST SOCIAL OUTING APP

## 1. Product Vision

**Rủ Đi** là một ứng dụng social dành cho nhóm bạn, giúp toàn bộ quá trình:

**Tìm chỗ đi → Rủ bạn → Lên kế hoạch → Đi chơi → Ăn uống → Chia tiền → Lưu kỷ niệm**

diễn ra trong **một ứng dụng duy nhất**, với một **AI companion sống bên trong mỗi nhóm bạn**.

AI không chỉ là chatbot để hỏi đáp.

AI phải hiểu:

* Nhóm này gồm những ai
* Mỗi người thích gì
* Nhóm thường đi đâu
* Budget của nhóm
* Người nào đã trả tiền
* Ai ăn món gì
* Ai còn nợ ai
* Những địa điểm từng đi
* Những kỷ niệm của nhóm
* Context toàn bộ chuyến đi

---

# 2. Core Product Loop

```text
DISCOVER
   ↓
CREATE PLAN
   ↓
INVITE FRIENDS
   ↓
GROUP CHAT
   ↓
GO OUT
   ↓
AI TRACKS ACTIVITIES
   ↓
SCAN RECEIPTS / EXPENSES
   ↓
AI SPLITS BILL
   ↓
SETTLEMENT
   ↓
SHARE MEMORIES
   ↓
AI LEARNS GROUP PREFERENCES
   ↓
BETTER RECOMMENDATIONS NEXT TIME
```

Đây phải là vòng lặp chính của sản phẩm.

---

# 3. PRODUCT PILLARS

Rủ Đi nên được xây quanh 5 pillar chính.

### Pillar 1 — Discover

Tìm nơi đi chơi.

### Pillar 2 — Group

Tổ chức hội bạn và chuyến đi.

### Pillar 3 — AI Companion

AI hiểu context của nhóm và chủ động hỗ trợ.

### Pillar 4 — Smart Expense

AI chia tiền tự động.

### Pillar 5 — Memories

Lưu lại lịch sử và kỷ niệm của nhóm.

---

# 4. MVP — MUST HAVE

MVP không nên cố làm Facebook + Grab + Splitwise + Locket ngay lập tức.

MVP nên chứng minh một proposition duy nhất:

> **Đi chơi với bạn bè trở nên dễ hơn đáng kể nhờ AI.**

---

# EPIC 01 — AUTHENTICATION & USER PROFILE

## F01 — Account Registration

Cho phép:

* Login bằng Apple
* Login bằng Google
* Login bằng số điện thoại
* OTP

### User data

```text
user_id
display_name
avatar
phone
email
date_of_birth
gender_optional
city
created_at
```

---

## F02 — Personal Profile

Profile cơ bản:

* Avatar
* Username
* Bio
* Thành phố
* Friend count
* Group count
* Trips count
* Places visited
* Memories count

---

# EPIC 02 — FRIEND GRAPH

## F03 — Add Friends

Có thể:

* Search username
* Search phone
* QR profile
* Invite link
* Contact sync

---

## F04 — Friend Request

States:

```text
pending
accepted
declined
blocked
```

---

## F05 — QR Friend Add

Một QR riêng cho mỗi user.

Ví dụ:

```text
ru-di.app/u/kiet
```

Scan QR → mở profile → Add friend.

---

# EPIC 03 — GROUP SYSTEM

Đây là object quan trọng nhất của ứng dụng.

## F06 — Create Group

Ví dụ:

```text
Hội Ăn Chơi Quận 1

Members:
Kiet
Nam
Huy
Linh
Mai
```

Group có:

```text
group_id
group_name
avatar
members
admins
created_at
```

---

## F07 — Group Chat

Chat realtime.

Support:

* Text
* Image
* Video
* Sticker
* Reaction
* Reply
* Mention
* Location
* Receipt
* Poll

---

## F08 — AI Member

Mỗi group mặc định có:

**Rủ Đi AI**

AI xuất hiện như một member.

Ví dụ:

```text
Kiet:
Tối nay ăn gì?

Nam:
Quận 1 nhé.

Linh:
Budget dưới 300k/người.

Rủ Đi AI:
Mình tìm được 4 quán phù hợp với cả nhóm 👀

1. Pizza 4P's
2. Bếp Mẹ Ỉn
3. Mâm Bắc
4. Som Tum Thai
```

Điểm quan trọng:

User **không nhất thiết phải @AI**.

AI có thể hiểu context group.

---

# EPIC 04 — DISCOVERY

## F09 — Discover Places

Các category:

```text
Ăn uống
Cafe
Bar
Đi chơi
Shopping
Cinema
Playground
Chill
Date
Outdoor
Nightlife
Activity
Staycation
Travel
```

---

## F10 — Place Detail

Thông tin:

* Photos
* Rating
* Address
* Price
* Distance
* Opening hours
* Description
* Tags
* Reviews
* Map
* Group suitability

---

## F11 — AI Place Match

Đây nên là một differentiator.

Ví dụ:

```text
AI MATCH: 94%
```

AI giải thích:

> Quán phù hợp vì nhóm thường thích đồ nướng, budget khoảng 250k/người và 4/6 thành viên từng lưu các quán tương tự.

---

## F12 — Natural Language Place Search

Ví dụ user search:

> quán chill quận 2 ngồi ngoài trời khoảng 200k/người đi 6 người

AI convert thành:

```text
location = Thu Duc / District 2
category = restaurant/cafe
ambience = chill
outdoor = true
budget <= 200k
group_size = 6
```

---

# EPIC 05 — OUTING / TRIP PLAN

## F13 — Create Outing

Ví dụ:

```text
Đà Lạt cuối tuần

17/10 → 19/10

Participants:
8

Budget:
2,500,000 / person
```

---

## F14 — Invite Members

Add từ:

* Group
* Friends
* Invite link

---

## F15 — Outing Timeline

Timeline:

```text
08:00 Cafe
10:00 Check-in
12:00 Lunch
14:00 Sightseeing
18:00 BBQ
21:00 Bar
```

---

## F16 — AI Itinerary Generator

Prompt:

> Đi Đà Lạt 2 ngày 1 đêm, 8 người, budget 2 triệu/người.

AI generate:

```text
Day 1

08:00
Lưng Chừng Cafe

10:30
Check-in homestay

12:00
Tiệm Nướng Xóm Lèo

15:00
Quảng trường

18:00
BBQ

21:00
Night market
```

---

## F17 — Voting

Nếu AI suggest 5 quán:

Members vote.

```text
Pizza 4P's      4 votes
Bếp Mẹ Ỉn       2 votes
Som Tum Thai    1 vote
```

---

# EPIC 06 — AI SMART BILL

Đây nên là **Hero Feature**.

---

# F18 — Receipt OCR

User chụp bill.

AI extract:

```text
Bò nướng       220k
Mì Ý           160k
Salad           90k
Beer x4        240k
Coke x2         60k
```

Total:

```text
770,000 VND
```

---

# F19 — Bill Item Detection

AI parse:

```json
{
  "items": [
    {
      "name": "Bò nướng",
      "quantity": 1,
      "price": 220000
    }
  ]
}
```

---

# F20 — Assign Food To Person

UI cho phép:

```text
Bò nướng

☑ Kiet
☑ Huy
☑ Nam
□ Linh
```

AI chia:

```text
220,000 / 3
```

---

# F21 — AI Person Recognition

Đây là feature advanced.

Khi tạo group:

User có thể upload ảnh group.

AI detect:

```text
Person 1
Person 2
Person 3
Person 4
```

User assign:

```text
Person 1 → Kiet
Person 2 → Nam
Person 3 → Linh
Person 4 → Huy
```

Sau đó AI tạo **person identity profile**.

---

# F22 — Visual Food Participation Detection

Trong chuyến đi:

User upload ảnh bàn ăn.

AI detect:

```text
Kiet
Nam
Huy
Linh
```

Sau đó kết hợp:

```text
Receipt
+
Table photos
+
Chat context
+
Manual corrections
```

để infer:

```text
Pizza:
Kiet
Nam
Huy

Beer:
Kiet
Huy

Juice:
Linh
```

AI phải luôn show:

```text
AI suggested
```

chứ không auto-charge ngay.

---

# F23 — Confidence Score

Ví dụ:

```text
Pizza

Kiet     98%
Nam      91%
Huy      88%
Linh     24%
```

Nếu confidence thấp:

AI hỏi:

> Linh có ăn pizza không?

---

# F24 — Expense Creation From Chat

Ví dụ:

```text
Kiet:
Tao trả Grab 180k rồi nhé.
```

AI detect:

```text
Expense detected

Grab
180,000 VND

Paid by:
Kiet

Split among:
6 people
```

Button:

```text
Confirm
```

---

# F25 — Expense Creation From Receipt

Upload receipt → tự tạo expense.

---

# F26 — Expense Creation From Screenshot

Ví dụ screenshot:

* Grab
* ShopeeFood
* Banking
* Restaurant receipt

AI extract automatically.

---

# F27 — Smart Settlement

Ví dụ:

```text
Kiet paid       2,100,000
Nam paid          500,000
Linh paid       1,400,000
Huy paid          200,000
```

System calculate minimum transfers.

Thay vì:

```text
20 transaction
```

AI simplify thành:

```text
Nam → Kiet     320k
Huy → Linh     450k
Mai → Kiet     210k
```

---

# F28 — Settlement Tracking

Status:

```text
Pending
Paid
Confirmed
```

---

# F29 — Payment Link / QR

Generate:

* Bank QR
* VietQR

Ví dụ:

```text
Pay Kiet
320,000 VND
```

---

# EPIC 07 — AI GROUP COMPANION

AI phải giống một member thật.

---

## F30 — Group Memory

AI nhớ:

```text
Kiet thích sushi
Nam không ăn cay
Linh ăn chay
Huy thích bar
Mai budget thấp
```

---

## F31 — Group Preference Profile

AI tạo implicit profile:

```text
Food

Japanese        0.91
BBQ             0.87
Vietnamese      0.76

Activity

Cafe            0.95
Cinema          0.81
Outdoor         0.62
```

---

## F32 — Proactive Suggestion

Ví dụ:

18:00 Friday.

AI:

> Cuối tuần rồi 👀 Nhóm mình 3 tuần chưa tụ tập. Có 5 quán mới gần mọi người, muốn xem không?

---

## F33 — Contextual Suggestions

Group chat:

```text
Nam:
Chán quá.

Kiet:
Đi đâu không?
```

AI:

> 4 người đang online, mình tìm vài chỗ gần trung tâm nhé?

---

## F34 — Budget Awareness

AI biết:

```text
Average group spend
Per-person budget
Previous spending
```

Ví dụ:

> Quán này khoảng 450k/người, cao hơn mức nhóm thường chi khoảng 180k.

---

# EPIC 08 — MEMORIES

---

## F35 — Group Memory Wall

Mỗi group có private wall.

Có:

* Photos
* Videos
* Posts
* Check-ins
* Memories

---

## F36 — Automatic Trip Album

Sau chuyến đi:

AI tạo:

```text
Đà Lạt 2026
```

tự gom:

* Photos
* Places
* Expenses
* Messages
* Highlights

---

## F37 — AI Highlight Reel

AI chọn:

```text
Top moments
Best photos
Funniest moments
```

Có thể generate:

**30-second memory video**

---

## F38 — Locket Style Widget

Optional later.

Home screen widget:

```text
Latest photo from friends
```

---

# EPIC 09 — SOCIAL FEED

Feature này nên để sau MVP.

---

## F39 — Post

User có thể post:

* Photo
* Video
* Place
* Trip
* Memory

---

## F40 — Reactions

```text
❤️
😂
🔥
😍
😮
```

---

## F41 — Comments

Comment trên memories/posts.

---

## F42 — Privacy

Post visibility:

```text
Only me
Friends
Group
Public
```

---

# EPIC 10 — MAP

## F43 — Social Map

Map hiển thị:

```text
Places friends visited
Trending places
Saved places
Recommended places
```

---

## F44 — Group Heatmap

Ví dụ:

```text
Your group mostly hangs out in:

District 1
District 3
Thu Duc
```

---

## F45 — Meet-in-the-middle

Feature cực hay.

Members:

```text
Kiet → Thu Duc
Nam → District 7
Huy → District 1
Linh → Binh Thanh
```

AI tìm:

> Địa điểm tối ưu để mọi người đi lại tương đối cân bằng.

---

# EPIC 11 — LOCATION AWARENESS

Optional.

Nếu members đồng ý share location:

AI có thể detect:

```text
4/6 members arrived
```

hoặc:

> Nam còn cách quán khoảng 12 phút.

---

# EPIC 12 — CHECK-IN

## F46 — Group Check-in

Check-in tại:

```text
Restaurant
Cafe
Activity
```

---

## F47 — Automatic Place Detection

GPS + venue matching:

> Nhóm đang ở Pizza 4P's?

```text
Yes
No
```

---

# EPIC 13 — AI TRIP SUMMARY

Sau mỗi outing.

AI generate:

```text
ĐÀ LẠT 2026

8 members

Places visited
12

Total spent
13,800,000 VND

Average/person
1,725,000 VND

Photos
326

Top spender
Kiet

Food hunter
Huy

Photographer
Linh
```

---

# EPIC 14 — GROUP ACHIEVEMENTS

Gamification.

Badges:

```text
Food Hunter
Cafe Master
Night Owl
Trip Planner
Bill Hero
Photographer
Explorer
```

---

# EPIC 15 — NOTIFICATION ENGINE

Examples:

### Outing reminder

> 18:30 tối nay: BBQ với Team HCM.

### Payment reminder

> Bạn còn 320k chưa thanh toán cho Kiet.

### Social

> Linh vừa thêm 12 ảnh vào chuyến Đà Lạt.

### Discovery

> Có 3 quán mới hợp gu nhóm bạn.

---

# 5. AI ARCHITECTURE

AI không nên chỉ là:

```text
User → LLM → response
```

Nên xây như:

```text
                     Rủ Đi AI
                        │
        ┌───────────────┼────────────────┐
        │               │                │
      Chat          Vision AI       Recommendation
        │               │                │
        │          Receipt OCR            │
        │          Face Recognition       │
        │          Food Detection         │
        │               │                 │
        └───────────────┼─────────────────┘
                        │
                  Group Context
                        │
                Group Memory Graph
                        │
                  User Preferences
```

---

# 6. GROUP MEMORY GRAPH

Đây có thể trở thành moat của product.

Ví dụ:

```text
GROUP: Team 404
│
├── Kiet
│   ├── likes: Japanese
│   ├── likes: cafe
│   ├── budget: medium
│
├── Nam
│   ├── likes: BBQ
│   ├── dislikes: spicy
│
├── Linh
│   ├── vegetarian
│
└── Group
    ├── avg_budget: 300k
    ├── favorite_area: District 1
    ├── favorite_activity: cafe
    └── usual_time: Saturday evening
```

Sau một thời gian:

AI biết nhóm này gần như một người bạn thật.

---

# 7. AI TOOLS

AI Agent nên có các tool:

```text
search_places()

search_restaurants()

search_events()

get_place_detail()

create_poll()

create_outing()

update_itinerary()

add_expense()

parse_receipt()

assign_bill_items()

calculate_split()

get_group_balance()

create_payment_request()

search_group_memories()

create_memory_album()

get_weather()

get_route()

get_member_preferences()
```

---

# 8. MVP PRIORITY

Nếu team chỉ có khoảng 3–6 tháng.

## P0 — MUST HAVE

```text
Authentication

Profile

Friends

Group

Group Chat

Create Outing

Discover Places

AI Place Recommendation

Receipt OCR

Bill Split

Expense Tracking

Settlement

Group Memories

AI Group Assistant
```

Đây là MVP thật sự.

---

# 9. P1 — AFTER PRODUCT MARKET SIGNAL

```text
AI group memory

Natural-language place search

Trip itinerary generator

Voting

Bank QR

AI expense detection from chat

Automatic trip album

Social map

Group achievements

Smart notifications
```

---

# 10. P2 — ADVANCED AI

```text
Face recognition

Person identification

Food/person attribution

Vision-based bill participation detection

Location-aware group assistant

Meet-in-the-middle location optimization

Proactive AI suggestions

AI highlight reel

AI-generated trip recap
```

---

# 11. P3 — SOCIAL NETWORK EXPANSION

Sau khi core product chạy tốt mới làm:

```text
Public social feed

Follow users

Creators

Local reviewers

Place communities

Public trips

Public collections

Influencer content
```

Không nên build quá sớm.

---

# 12. HOME SCREEN

Một home tốt có thể gồm:

```text
Tonight?

Rủ hội bạn đi đâu đó 👀

[ Ask Rủ Đi AI ]

────────────

Your Groups

Team 404
Weekend Gang
Đà Lạt Crew

────────────

AI Picks For You

95% match
92% match
89% match

────────────

Upcoming

Saturday
Dinner with Team 404

────────────

Your Memories

Đà Lạt
12 photos
```

---

# 13. BOTTOM NAVIGATION

Đề xuất 5 tab:

```text
Explore

Plans

+

Groups

Profile
```

Button `+` mở:

```text
Create outing
Create expense
Post memory
Create group
```

---

# 14. AI BUTTON

Có thể có một AI orb luôn accessible.

```text
✦
```

Tap:

> Hôm nay muốn đi đâu?

Hoặc:

> Tối nay nhóm mình rảnh không?

---

# 15. KEY USER STORIES

### Story 01

As a user,

I want to create a group of friends,

so that we can organize outings together.

---

### Story 02

As a group,

we want AI to recommend places everyone might like,

so that we don't spend 30 minutes debating where to go.

---

### Story 03

As a user,

I want to photograph a receipt,

so that I don't need to manually type every expense.

---

### Story 04

As a group member,

I want to specify what I ate,

so that I only pay for what I consumed.

---

### Story 05

As a group,

we want AI to remember our preferences,

so future recommendations become better.

---

### Story 06

As a group,

we want one place where all trip photos and memories are stored.

---

# 16. PRODUCT NORTH STAR

Không nên dùng:

```text
MAU
Downloads
```

làm north star chính.

Đề xuất:

# Successful Group Outings / Month

Một **Successful Outing** có thể được define khi:

```text
≥ 3 members

AND

at least one:
- place selected
- expense created
- memory created
```

---

# 17. IMPORTANT PRODUCT METRICS

### Activation

```text
Signup → join/create group
```

### Group activation

```text
Group created
↓
≥3 members
↓
first outing
```

### AI usage

```text
AI queries / outing

AI recommendations accepted %

AI-generated expense confirmation %
```

### Expense

```text
Receipts scanned

Expenses auto-detected

AI split acceptance rate

Manual correction rate
```

### Retention

```text
D1
D7
D30
```

Quan trọng nhất:

```text
Group Retention
```

không phải individual retention.

---

# 18. AI QUALITY METRICS

Receipt OCR:

```text
Item recognition accuracy
Price accuracy
Total accuracy
```

Bill AI:

```text
Person-item assignment accuracy
User correction rate
```

Recommendation:

```text
Click rate
Save rate
Vote rate
Visit conversion
```

AI assistant:

```text
Suggestion acceptance rate
```

---

# 19. MONETIZATION

Không nên monetize quá sớm.

Sau khi có traction:

## Rủ Đi Plus

Ví dụ:

```text
49k/month
```

Features:

```text
Unlimited AI planning

Advanced AI split

Unlimited receipt scans

AI memory video

Travel planner

Advanced group statistics
```

---

# 20. BUSINESS MODEL — LOCAL DISCOVERY

Revenue lớn hơn có thể đến từ local businesses.

Ví dụ:

Restaurant:

```text
Promoted placement

Sponsored recommendation

Booking commission

Voucher commission
```

Quan trọng:

**Sponsored results phải được đánh dấu rõ ràng.**

Không được phá recommendation quality.

---

# 21. LONG-TERM VISION

Nếu product thành công, Rủ Đi không chỉ là một bill splitting app.

Nó trở thành:

# Social Operating System for Real-World Friend Groups

Tương tự:

```text
Instagram
→ online social graph

Rủ Đi
→ offline social graph
```

App hiểu:

```text
Ai hay đi với ai

Đi đâu

Ăn gì

Chi bao nhiêu

Khi nào đi

Gu của group

Kỷ niệm gì đã xảy ra
```

---

# 22. PRODUCT DIFFERENTIATION

Không nên positioning là:

> Splitwise có AI.

Mà nên là:

> **AI companion cho đời sống social ngoài đời thật.**

Bill splitting chỉ là **killer entry point**.

Social graph + group memory + local discovery mới là **long-term moat**.

---

# 23. RECOMMENDED DEVELOPMENT ORDER

## Phase 1 — Foundation

```text
Auth

User

Friend

Group

Group Chat
```

## Phase 2 — Outing

```text
Discover

Place

Create Plan

Voting

Trip
```

## Phase 3 — Money

```text
Expense

Receipt OCR

Bill Split

Balance

Settlement
```

## Phase 4 — AI

```text
Group AI

Recommendation

Group Memory

Expense AI
```

## Phase 5 — Memories

```text
Photos

Posts

Trip Album

Group Wall
```

## Phase 6 — Advanced AI

```text
Vision

Face Recognition

Food Recognition

Automatic Person-Food Mapping

Proactive AI
```

---

# 24. THE MOST IMPORTANT MVP FLOW

Đây là flow em sẽ yêu cầu team dev build polished nhất:

```text
Kiet tạo group
       ↓
Invite 5 friends
       ↓
"Kèo tối nay ăn gì?"
       ↓
AI recommend 5 places
       ↓
Group vote
       ↓
Create outing
       ↓
Go restaurant
       ↓
Take photos
       ↓
Take receipt photo
       ↓
AI reads receipt
       ↓
AI suggests who ate what
       ↓
Members confirm
       ↓
AI calculates settlement
       ↓
VietQR payment
       ↓
Trip completed
       ↓
AI creates memory album
```

Nếu flow này hoạt động cực mượt thì app đã có một value proposition rất mạnh.

---

# 25. ONE-LINE PRODUCT PITCH

> **Rủ Đi là AI companion cho hội bạn — giúp tìm chỗ đi, lên kèo, chia tiền và lưu lại mọi kỷ niệm trong một nơi.**

Hoặc ngắn hơn:

> **Rủ Đi — AI cho những cuộc vui ngoài đời.**
