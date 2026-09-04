import { ImageSource } from "expo-image";

import type { PlaceCategory } from "./places";
import { bangMauFixture, mauSang, mauSao } from "./theme";

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
  category: PlaceCategory;
  image: ImageSource;
};

export type ItinerarySlot = {
  time: string;
  title: string;
  icon: string;
  color: string;
  placeId?: string;
};

export type ItineraryDay = {
  day: string;
  items: ItinerarySlot[];
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
};

export const PEOPLE: DemoPerson[] = [
  { id: "minh-anh", name: "Minh Anh", initials: "MA", color: bangMauFixture.doHong },
  { id: "tuan-kiet", name: "Tuấn Kiệt", initials: "TK", color: mauSang.ai },
  { id: "thu-trang", name: "Thu Trang", initials: "TT", color: mauSao.dam },
  { id: "quang-huy", name: "Quang Huy", initials: "QH", color: bangMauFixture.xanhBien },
  { id: "lan-anh", name: "Lan Anh", initials: "LA", color: bangMauFixture.xanhLa },
  { id: "minh-khoa", name: "Minh Khoa", initials: "MK", color: bangMauFixture.camDam },
  { id: "hai-yen", name: "Hải Yến", initials: "HY", color: bangMauFixture.hongDam },
  { id: "thanh-phuc", name: "Thanh Phúc", initials: "TP", color: bangMauFixture.xanhDam },
];

export const COLLECTOR_INDEX = 0;

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
    category: "Quán ăn",
    image: demoAssets.cafe,
  },
  {
    id: "banh-can-le",
    name: "Bánh căn Lệ",
    subtitle: "Bánh căn nóng, hàng quen của dân địa phương",
    rating: "4.6",
    reviews: 188,
    distance: "900 m",
    price: "40K - 80K/người",
    match: 86,
    tags: ["Món local", "Bình dân"],
    category: "Quán ăn",
    image: demoAssets.dalatFriends,
  },
  {
    id: "lau-ga-la-e",
    name: "Lẩu gà lá é Gốc",
    subtitle: "Lẩu gà đặc sản, đủ chỗ nhóm 8",
    rating: "4.7",
    reviews: 214,
    distance: "1,6 km",
    price: "180K - 260K/người",
    match: 91,
    tags: ["Lẩu", "Nhóm đông"],
    category: "Quán ăn",
    image: demoAssets.wood,
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
    category: "Cafe",
    image: demoAssets.dalatFriends,
  },
  {
    id: "tiem-tra-suong",
    name: "Tiệm trà Sương",
    subtitle: "Trà thảo mộc, bàn dài ngoài trời",
    rating: "4.5",
    reviews: 143,
    distance: "2,1 km",
    price: "80K - 140K/người",
    match: 81,
    tags: ["Trà", "Ngoài trời"],
    category: "Cafe",
    image: demoAssets.cafe,
  },
  {
    id: "the-coffee-hill",
    name: "The Coffee Hill",
    subtitle: "Espresso và bánh, nhìn ra thung lũng",
    rating: "4.4",
    reviews: 301,
    distance: "2,4 km",
    price: "90K - 160K/người",
    match: 79,
    tags: ["Cà phê", "View đẹp"],
    category: "Cafe",
    image: demoAssets.road,
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
    category: "Vui chơi",
    image: demoAssets.road,
  },
  {
    id: "doi-thien-phuc",
    name: "Đồi Thiên Phúc Đức",
    subtitle: "Săn mây sáng sớm",
    rating: "4.5",
    reviews: 276,
    distance: "3,1 km",
    price: "0K - 50K/người",
    match: 90,
    tags: ["Săn mây", "Ngoài trời"],
    category: "Vui chơi",
    image: demoAssets.friends,
  },
  {
    id: "thung-lung-tinh-yeu",
    name: "Thung lũng Tình Yêu",
    subtitle: "Vườn hoa, hồ, góc sống ảo",
    rating: "4.3",
    reviews: 620,
    distance: "2,8 km",
    price: "150K - 220K/người",
    match: 77,
    tags: ["Hoa", "Chụp ảnh"],
    category: "Vui chơi",
    image: demoAssets.dalatFriends,
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
    category: "Đi chơi đêm",
    image: demoAssets.friends,
  },
  {
    id: "pho-di-bo-dem",
    name: "Phố đi bộ đêm",
    subtitle: "Nhạc sống, đèn, trà sữa",
    rating: "4.2",
    reviews: 190,
    distance: "1,1 km",
    price: "60K - 120K/người",
    match: 76,
    tags: ["Đi đêm", "Nhộn nhịp"],
    category: "Đi chơi đêm",
    image: demoAssets.cafe,
  },
  {
    id: "ho-tuyen-lam-dem",
    name: "Hồ Tuyền Lâm về đêm",
    subtitle: "BBQ và lửa trại ven hồ",
    rating: "4.6",
    reviews: 155,
    distance: "4,2 km",
    price: "200K - 320K/người",
    match: 89,
    tags: ["BBQ", "Đi đêm"],
    category: "Đi chơi đêm",
    image: demoAssets.wood,
  },
];

export const ITINERARY_SEED: ItineraryDay[] = [
  {
    day: "Ngày 1 - 17/10 (Thứ Bảy)",
    items: [
      { time: "07:00", title: "Khởi hành từ TP.HCM", icon: "car-outline", color: bangMauFixture.cam },
      { time: "11:00", title: "Check-in homestay", icon: "home-outline", color: mauSang.ai },
      { time: "12:30", title: "Ăn trưa - Bánh căn Lệ", icon: "restaurant-outline", color: bangMauFixture.camDam, placeId: "banh-can-le" },
      { time: "14:30", title: "Ga Đà Lạt và Dinh Bảo Đại", icon: "camera-outline", color: bangMauFixture.xanhLa },
      { time: "18:00", title: "BBQ bên hồ Tuyền Lâm", icon: "flame-outline", color: bangMauFixture.do, placeId: "ho-tuyen-lam-dem" },
      { time: "20:00", title: "Chợ đêm Đà Lạt", icon: "moon-outline", color: mauSang.ai, placeId: "cho-dem" },
    ],
  },
  {
    day: "Ngày 2 - 18/10 (Chủ Nhật)",
    items: [
      { time: "06:30", title: "Săn mây đồi Thiên Phúc Đức", icon: "cloud-outline", color: bangMauFixture.xanhTroi, placeId: "doi-thien-phuc" },
      { time: "09:00", title: "Cafe sáng - Still Cafe", icon: "cafe-outline", color: bangMauFixture.vangSam, placeId: "still-cafe" },
      { time: "11:30", title: "Mua đặc sản", icon: "bag-handle-outline", color: bangMauFixture.xanhLaNhat },
      { time: "15:00", title: "Picnic và chụp ảnh", icon: "images-outline", color: bangMauFixture.hong },
      { time: "19:30", title: "Lẩu gà lá é", icon: "restaurant-outline", color: bangMauFixture.cam, placeId: "lau-ga-la-e" },
    ],
  },
  {
    day: "Ngày 3 - 19/10 (Thứ Hai)",
    items: [{ time: "09:00", title: "Trả phòng và về lại Sài Gòn", icon: "bus-outline", color: bangMauFixture.ngoc }],
  },
];

/** Kept as an alias so older imports keep compiling while screens move to the session clone. */
export const ITINERARY = ITINERARY_SEED;

export const BILL_ITEMS = [
  { name: "Lẩu gà lá é", amount: 450_000, people: [0, 1, 2, 3] },
  { name: "Bò nướng", amount: 560_000, people: [1, 3] },
  { name: "Nước ngọt", amount: 75_000, people: [0, 2, 4] },
  { name: "Trà tắc", amount: 45_000, people: [0, 2, 3] },
  { name: "Khăn lạnh", amount: 20_000, people: [0, 1, 2, 3] },
  { name: "Phí phục vụ", amount: 130_000, people: [0, 1, 2, 3, 4, 5, 6, 7] },
] as const;

/**
 * The rest of the canonical trip (3.840.000 − 1.280.000). Not the Xóm Lèo bill.
 * Split across all eight people so trip total and personal spend stay one story.
 */
export const OTHER_TRIP_ITEMS = [
  { name: "Homestay Pine Hill", amount: 2_000_000, people: [0, 1, 2, 3, 4, 5, 6, 7] },
  { name: "Xăng xe khứ hồi", amount: 560_000, people: [0, 1, 2, 3, 4, 5, 6, 7] },
] as const;

export const MEMORY_PHOTOS: ImageSource[] = [
  demoAssets.dalatFriends,
  demoAssets.cafe,
  demoAssets.road,
  demoAssets.friends,
  demoAssets.cafe,
  demoAssets.dalatFriends,
  demoAssets.friends,
  demoAssets.road,
];

export const MEMORY_VIDEO_INDEXES = [2, 6] as const;

export const VOTE_PLACE_IDS = ["xom-leo", "still-cafe", "puppy-farm"] as const;

export function cloneItinerary(source: ItineraryDay[] = ITINERARY_SEED): ItineraryDay[] {
  return source.map((day) => ({
    day: day.day,
    items: day.items.map((item) => ({ ...item })),
  }));
}

export const formatVnd = (value: number) => `${value.toLocaleString("vi-VN")}đ`;
