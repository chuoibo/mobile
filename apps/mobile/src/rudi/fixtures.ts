import { ImageSource } from "expo-image";

export type DemoPerson = {
  id: string;
  name: string;
  initials: string;
  color: string;
};

export type DemoPlace = {
  id: string;
  name: string;
  subtitle: string;
  rating: string;
  reviews: number;
  distance: string;
  price: string;
  match: number;
  tags: string[];
  image: ImageSource;
};

export const demoAssets = {
  friends: require("../../assets/rudi/friends-rooftop.jpg") as ImageSource,
  cafe: require("../../assets/rudi/dalat-cafe.jpg") as ImageSource,
  dalatFriends: require("../../assets/rudi/dalat-friends.jpg") as ImageSource,
  road: require("../../assets/rudi/vietnam-road.jpg") as ImageSource,
  wood: require("../../assets/rudi/dark-wood-grain.jpg") as ImageSource,
};

export const DEMO_GROUP = {
  id: "team-da-lat",
  name: "Team Đà Lạt",
  tripName: "Đà Lạt cuối tuần",
  dateRange: "17/10/2026 - 19/10/2026",
  budgetPerPersonVnd: 2_500_000,
  billTotalVnd: 1_280_000,
  tripTotalVnd: 3_840_000,
  photos: 256,
  videos: 18,
  checkIns: 12,
};

export const PEOPLE: DemoPerson[] = [
  { id: "minh-anh", name: "Minh Anh", initials: "MA", color: "#E85D75" },
  { id: "tuan-kiet", name: "Tuấn Kiệt", initials: "TK", color: "#7D49EF" },
  { id: "thu-trang", name: "Thu Trang", initials: "TT", color: "#F59E0B" },
  { id: "quang-huy", name: "Quang Huy", initials: "QH", color: "#0891B2" },
  { id: "lan-anh", name: "Lan Anh", initials: "LA", color: "#16A34A" },
  { id: "minh-khoa", name: "Minh Khoa", initials: "MK", color: "#EA580C" },
  { id: "hai-yen", name: "Hải Yến", initials: "HY", color: "#DB2777" },
  { id: "thanh-phuc", name: "Thanh Phúc", initials: "TP", color: "#2563EB" },
];

export const PLACES: DemoPlace[] = [
  {
    id: "xom-leo",
    name: "Tiệm Nướng Xóm Lèo",
    subtitle: "Nướng thơm lừng, view đồi cực chill",
    rating: "4.8",
    reviews: 256,
    distance: "1,2 km",
    price: "150K - 250K/người",
    match: 95,
    tags: ["Chill", "View đẹp", "Nhóm đông"],
    image: demoAssets.cafe,
  },
  {
    id: "still-cafe",
    name: "Still Cafe Đà Lạt",
    subtitle: "Cà phê view đồi, không gian yên",
    rating: "4.7",
    reviews: 512,
    distance: "1,8 km",
    price: "120K - 200K/người",
    match: 92,
    tags: ["Cà phê", "Nhẹ nhàng", "Ngoài trời"],
    image: demoAssets.dalatFriends,
  },
  {
    id: "puppy-farm",
    name: "Puppy Farm Đà Lạt",
    subtitle: "Nông trại hoa và nhiều góc ảnh",
    rating: "4.6",
    reviews: 398,
    distance: "2,3 km",
    price: "100K - 180K/người",
    match: 88,
    tags: ["Outdoor", "Hoa", "Chụp ảnh"],
    image: demoAssets.road,
  },
  {
    id: "cho-dem",
    name: "Chợ Đêm Đà Lạt",
    subtitle: "Ăn vặt, mua sắm, không khí vui",
    rating: "4.5",
    reviews: 821,
    distance: "700 m",
    price: "80K - 150K/người",
    match: 84,
    tags: ["Món local", "Đi đêm", "Nhộn nhịp"],
    image: demoAssets.friends,
  },
];

export const ITINERARY = [
  {
    day: "Ngày 1 - 17/10 (Thứ Bảy)",
    items: [
      ["07:00", "Khởi hành từ TP.HCM", "car-outline", "#F97316"],
      ["11:00", "Check-in homestay", "home-outline", "#7D49EF"],
      ["12:30", "Ăn trưa - Bánh căn Lệ", "restaurant-outline", "#EA580C"],
      ["14:30", "Ga Đà Lạt và Dinh Bảo Đại", "camera-outline", "#16A34A"],
      ["18:00", "BBQ bên hồ Tuyền Lâm", "flame-outline", "#E11D48"],
      ["20:00", "Chợ đêm Đà Lạt", "moon-outline", "#7D49EF"],
    ],
  },
  {
    day: "Ngày 2 - 18/10 (Chủ Nhật)",
    items: [
      ["06:30", "Săn mây đồi Thiên Phúc Đức", "cloud-outline", "#0EA5E9"],
      ["09:00", "Cafe sáng - Still Cafe", "cafe-outline", "#A16207"],
      ["11:30", "Mua đặc sản", "bag-handle-outline", "#65A30D"],
      ["15:00", "Picnic và chụp ảnh", "images-outline", "#EC4899"],
      ["19:30", "Lẩu gà lá é", "restaurant-outline", "#F97316"],
    ],
  },
  {
    day: "Ngày 3 - 19/10 (Thứ Hai)",
    items: [["09:00", "Trả phòng và về lại Sài Gòn", "bus-outline", "#0D9488"]],
  },
] as const;

export const BILL_ITEMS = [
  { name: "Lẩu gà lá é", amount: 450_000, people: [0, 1, 2, 3] },
  { name: "Bò nướng", amount: 560_000, people: [1, 3] },
  { name: "Nước ngọt", amount: 75_000, people: [0, 2, 4] },
  { name: "Trà tắc", amount: 45_000, people: [0, 2, 3] },
  { name: "Khăn lạnh", amount: 20_000, people: [0, 1, 2, 3] },
  { name: "Phí phục vụ", amount: 130_000, people: [0, 1, 2, 3, 4, 5, 6, 7] },
] as const;

export const formatVnd = (value: number) => `${value.toLocaleString("vi-VN")}đ`;
