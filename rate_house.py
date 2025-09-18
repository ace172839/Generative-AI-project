import requests
from collections import Counter

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# 預設搜尋半徑為 1000 公尺 (1公里)
def find_nearby_amenities_with_counts(lat, lon, radius_meters=1000):
    """
    查詢指定座標附近的設施，包含三鐵車站，並回傳各設施的「標籤」與「數量」。
    """
    
    query_template = f"""
    [out:json][timeout:30];
    (
      node["food"~"restaurant|cafe|fast_food"](around:{radius_meters},{lat},{lon});
      node["shop"~"convenience|supermarket"](around:{radius_meters},{lat},{lon});
      node["health"="hospital|clinic|dentist|pharmacy"](around:{radius_meters},{lat},{lon});
      node["leisure"="park|cinema"](around:{radius_meters},{lat},{lon});
      node["amenity"="fuel|post_office|atm|bank"](around:{radius_meters},{lat},{lon});
      node["transport"="bus_stop"](around:{radius_meters},{lat},{lon});

      // 三鐵車站查詢
      node["railway"="station"]["network"~"捷運"](around:{radius_meters},{lat},{lon});
      node["railway"="station"]["operator"~"捷運"](around:{radius_meters},{lat},{lon});
      node["railway"="station"]["network"~"臺灣鐵路|台鐵"](around:{radius_meters},{lat},{lon});
      node["railway"="station"]["operator"~"臺灣鐵路|台鐵"](around:{radius_meters},{lat},{lon});
      node["railway"="station"]["network"~"台灣高速鐵路|高鐵"](around:{radius_meters},{lat},{lon});
      node["railway"="station"]["operator"~"台灣高速鐵路|高鐵"](around:{radius_meters},{lat},{lon});
    );
    out body;
    """
    
    print(f"--- 正在以 {radius_meters} 公尺為半徑，發送包含三鐵的查詢 ---")
    
    try:
        response = requests.post(OVERPASS_API_URL, data=query_template.encode('utf-8'), timeout=30)
        response.raise_for_status()
        data = response.json()
        
        all_found_tags = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            
            network = tags.get("network", "")
            operator = tags.get("operator", "")
            
            is_station = False
            if "捷運" in network or "捷運" in operator:
                all_found_tags.append("mrt_station")
                is_station = True
            elif "臺灣鐵路" in network or "台鐵" in network or "臺灣鐵路" in operator or "台鐵" in operator:
                all_found_tags.append("tra_station")
                is_station = True
            elif "台灣高速鐵路" in operator or "高鐵" in operator or "台灣高速鐵路" in network or "高鐵" in network:
                all_found_tags.append("hsr_station")
                is_station = True
            
            # 如果不是車站，再判斷是否為其他一般設施
            if not is_station:
                tag_value = (
                    tags.get("amenity") or 
                    tags.get("shop") or 
                    tags.get("leisure") or 
                    tags.get("highway")
                )
                if tag_value:
                    all_found_tags.append(tag_value)

        return Counter(all_found_tags)
        
    except requests.exceptions.RequestException as e:
        print(f"查詢 OSM 時發生網路錯誤: {e}")
        return Counter()
    except Exception as e:
        print(f"處理資料時發生未知錯誤: {e}")
        return Counter()

# --- 測試 ---
# 這次我們用「台北車站」附近的座標來測試，這樣才能同時找到三鐵
property_lat = 25.0479
property_lon = 121.5173

# 將搜尋半徑擴大到 1000 公尺 (1公里)，因為車站通常比較遠
amenity_counts = find_nearby_amenities_with_counts(property_lat, property_lon, radius_meters=1000)

print(f"\n在座標 ({property_lat}, {property_lon}) 附近找到的設施與數量:")
if amenity_counts:
    for amenity, count in amenity_counts.most_common():
        print(f"- {amenity}: {count} 個")
else:
    print("沒有找到任何符合條件的設施。")

# --- 更新生活機能規則判斷 ---
def check_living_function_updated(counts):
    score = 0
    # ... 其他規則 ...

    # 交通便利性規則
    if counts.get('mrt_station', 0) > 0:
        score += 1
        print("\n[評分] 交通機能：鄰近捷運")
    if counts.get('tra_station', 0) > 0:
        score += 1
        print("[評分] 交通機能：鄰近台鐵")
    if counts.get('hsr_station', 0) > 0:
        score += 1
        print("[評分] 交通機能：鄰近高鐵")
        
    return f"綜合評分: {score}"

print("\n--- 生活機能規則判斷 ---")
print(check_living_function_updated(amenity_counts))