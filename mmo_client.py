import tkinter as tk
import websocket
import json
import threading
import random
import math
import time

class BaldursGateVibeClient:
    def __init__(self, root):
        self.root = root
        self.root.title("MX Linux WoW Cleave & Particle Engine")
        
        self.SCREEN_W, self.SCREEN_H = 1920, 1200
        self.WORLD_SIZE = 4000
        
        self.root.geometry(f"{self.SCREEN_W}x{self.SCREEN_H}+0+0")
        self.root.attributes("-fullscreen", True)
        
        self.canvas = tk.Canvas(root, width=self.SCREEN_W, height=self.SCREEN_H, bg="#32382c", highlightthickness=0)
        self.canvas.pack()

        self.my_id, self.px, self.py = None, 400, 400
        self.players_data = {}
        self.monsters_data = []
        self.cities = {}
        self.my_inventory = []
        self.current_zone = "Loading Area..."
        self.show_map = False
        self.show_character_sheet = False
        self.show_merchant = False
        
        self.notification_text = ""
        self.notification_timer = 0.0
        
        self.facing_angle = 0.0 
        self.active_fx = []
        
        # Cooldown markers
        self.aoe_cooldown_duration = 5.0
        self.last_aoe_cast_time = 0.0
        self.last_global_cast_time = 0.0

        self.grass_noise_map = []
        grass_colors = ["#394032", "#2d3327", "#424a3a", "#252b20", "#4d3d28"]
        for _ in range(800):
            self.grass_noise_map.append({
                "x": random.randint(0, self.WORLD_SIZE),
                "y": random.randint(0, self.WORLD_SIZE),
                "color": random.choice(grass_colors)
            })

        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<KeyPress>", self.handle_movement)
        self.root.bind("e", lambda e: self.trigger_eat())
        self.root.bind("m", lambda e: self.toggle_map())
        self.root.bind("c", lambda e: self.toggle_character_sheet())
        self.root.bind("b", lambda e: self.toggle_merchant_shop())
        self.root.bind("1", lambda e: self.cast_missile())
        self.root.bind("2", lambda e: self.cast_cleave())
        self.root.bind("3", lambda e: self.cast_aoe_nova())
        self.canvas.bind("<Button-1>", self.handle_canvas_click)

        self.ws = websocket.WebSocketApp("ws://localhost:8080", on_message=self.on_message)
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

        self.last_seen_healths = {}
        self.render_tick()

    def on_message(self, ws, msg):
        data = json.loads(msg)
        if data["type"] == "welcome":
            self.my_id = data["id"]
            self.cities = data["cities"]
            
        elif data["type"] == "shop_response":
            # ---> THIS WAITS FOR THE SERVER'S ANSWER <---
            print(data["message"])  # Prints to your terminal!
            self.notification_text = data["message"]
            self.notification_timer = time.time() + 3.0  # Shows on screen for 3s
            
        elif data["type"] == "update":
            self.players_data = data["players"]
            self.monsters_data = data.get("monsters", [])
            if self.my_id in self.players_data:
                self.my_inventory = self.players_data[self.my_id]["inventory"]
                self.current_zone = self.players_data[self.my_id]["currentCity"]
            self.process_combat_numbers()
            
    def process_combat_numbers(self):
        for mob in self.monsters_data:
            m_id = mob["id"]
            if m_id in self.last_seen_healths:
                diff = self.last_seen_healths[m_id] - mob["hp"]
                if diff > 0:
                    self.spawn_floating_text(mob["x"], mob["y"], f"-{diff}", "#ff5555")
            self.last_seen_healths[m_id] = mob["hp"]

        for p_id, p in self.players_data.items():
            if p_id in self.last_seen_healths:
                diff = self.last_seen_healths[p_id] - p["hp"]
                if diff > 0:
                    self.spawn_floating_text(p["x"], p["y"], f"-{diff}", "#ff5555")
                elif diff < 0:
                    self.spawn_floating_text(p["x"], p["y"], f"+{abs(diff)}", "#50fa7b")
            self.last_seen_healths[p_id] = p["hp"]

    def spawn_floating_text(self, world_x, world_y, text, color):
        self.active_fx.append({
            "type": "floating_text", "wx": world_x, "wy": world_y,
            "text": text, "color": color, "life": 1.0, "y_off": 0
        })

    def handle_movement(self, event):
        if not self.my_id: return
        step = 24
        dx, dy = 0, 0
        if event.char == 'w' or event.keysym == 'Up': dy = -step
        elif event.char == 's' or event.keysym == 'Down': dy = step
        elif event.char == 'a' or event.keysym == 'Left': dx = -step
        elif event.char == 'd' or event.keysym == 'Right': dx = step
        
        if dx != 0 or dy != 0:
            self.facing_angle = math.atan2(dy, dx)
            self.px = max(40, min(self.WORLD_SIZE - 40, self.px + dx))
            self.py = max(40, min(self.WORLD_SIZE - 40, self.py + dy))
            try: 
                self.ws.send(json.dumps({"type": "move", "x": self.px, "y": self.py}))
            except: 
                pass

    def trigger_eat(self):
        if not self.my_id: return
        try: 
            self.ws.send(json.dumps({"type": "eat_item"}))
        except: 
            pass

    def toggle_character_sheet(self):
        self.show_character_sheet = not self.show_character_sheet

    def toggle_merchant_shop(self):
        if self.current_zone != "Wilderness":
            self.show_merchant = not self.show_merchant
        else:
            self.spawn_floating_text(self.px, self.py, "Must be in City!", "#ff5555")
    def handle_canvas_click(self, event):
        if not self.my_id: return
        
        if self.show_merchant:
            mx = self.SCREEN_W // 2 - 200
            my = self.SCREEN_H // 2 - 250
            
            # Steel Broadsword
            if mx + 30 <= event.x <= mx + 370 and my + 110 <= event.y <= my + 180:
                try:
                    self.ws.send(json.dumps({
                        "type": "buy_item", 
                        "itemName": "Steel Broadsword", 
                        "cost": 50
                    }))
                    self.notification_text = "✨ Purchased Steel Broadsword!"
                    self.notification_timer = time.time() + 3.0  # Show for 3 seconds
                except:
                    pass
            
            # Iron Plate Mail
            elif mx + 30 <= event.x <= mx + 370 and my + 200 <= event.y <= my + 270:
                try:
                    self.ws.send(json.dumps({
                        "type": "buy_item", 
                        "itemName": "Iron Plate Mail", 
                        "cost": 75
                    }))
                    self.notification_text = "🛡️ Purchased Iron Plate Mail!"
                    self.notification_timer = time.time() + 3.0  # Show for 3 seconds
                except:
                    pass

    def cast_missile(self):
        if not self.my_id: return
        now = time.time()
        if now - self.last_global_cast_time < 0.2: return
        
        try:
            self.ws.send(json.dumps({"type": "cast_spell", "damage": 15, "range": 350}))
            self.last_global_cast_time = now 
            cx, cy = self.SCREEN_W // 2, self.SCREEN_H // 2
            self.active_fx.append({
                "type": "missile", "x": cx, "y": cy,
                "vx": math.cos(self.facing_angle) * 16, "vy": math.sin(self.facing_angle) * 16,
                "life": 1.0
            })
        except: 
            pass

    def cast_cleave(self):
        if not self.my_id: return
        now = time.time()
        if now - self.last_global_cast_time < 0.2: return
        
        try:
            self.ws.send(json.dumps({"type": "cast_spell", "damage": 30, "range": 120}))
            self.last_global_cast_time = now
            self.active_fx.append({
                "type": "cleave_arc", "cx": self.SCREEN_W // 2, "cy": self.SCREEN_H // 2,
                "base_angle": self.facing_angle, "radius": 20, "life": 1.0
            })
        except: 
            pass

    def cast_aoe_nova(self):
        if not self.my_id: return
        now = time.time()
        if now - self.last_global_cast_time < 0.2: return
        if now - self.last_aoe_cast_time < self.aoe_cooldown_duration: return
        
        try:
            self.ws.send(json.dumps({"type": "cast_spell", "damage": 45, "range": 250}))
            self.last_aoe_cast_time = now
            self.last_global_cast_time = now 
            self.active_fx.append({
                "type": "nova_blast", "cx": self.SCREEN_W // 2, "cy": self.SCREEN_H // 2,
                "radius": 10, "life": 1.0
            })
        except: 
            pass

    def toggle_map(self): 
        self.show_map = not self.show_map

    def render_tick(self):
        self.canvas.delete("all") 
        cam_x = self.px - (self.SCREEN_W / 2)
        cam_y = self.py - (self.SCREEN_H / 2)

        for node in self.grass_noise_map:
            rx = node["x"] - cam_x
            ry = node["y"] - cam_y
            if 0 <= rx <= self.SCREEN_W and 0 <= ry <= self.SCREEN_H:
                self.canvas.create_line(rx, ry, rx+6, ry-5, fill=node["color"], width=2)

        for name, data in self.cities.items():
            cx = data["x"] - cam_x
            cy = data["y"] - cam_y
            self.canvas.create_oval(cx-350, cy-350, cx+350, cy+350, outline="#a6e3a1", width=4, dash=(4,4))
            self.canvas.create_text(cx, cy-370, text=f"🛡️ {name.upper()}", fill="#a6e3a1", font=("Courier", 18, "bold"))

        if not hasattr(self, 'smooth_mobs'):
            self.smooth_mobs = {}

        for mob in self.monsters_data:
            m_id = mob["id"]
            if m_id not in self.smooth_mobs:
                self.smooth_mobs[m_id] = {"x": mob["x"], "y": mob["y"]}
            
            self.smooth_mobs[m_id]["x"] += (mob["x"] - self.smooth_mobs[m_id]["x"]) * 0.15
            self.smooth_mobs[m_id]["y"] += (mob["y"] - self.smooth_mobs[m_id]["y"]) * 0.15

            mx = self.smooth_mobs[m_id]["x"] - cam_x
            my = self.smooth_mobs[m_id]["y"] - cam_y

            if 0 <= mx <= self.SCREEN_W and 0 <= my <= self.SCREEN_H:
                self.canvas.create_oval(mx-18, my-18, mx+18, my+18, fill=mob["color"], outline="#11111b", width=2)
                self.canvas.create_rectangle(mx-20, my-28, mx+20, my-24, fill="#585b70")
                self.canvas.create_rectangle(mx-20, my-28, mx-20 + (40 * (mob["hp"]/mob["maxHp"])), my-24, fill="#f38ba8")
                self.canvas.create_text(mx, my-38, text=m_id, fill="#f38ba8", font=("Courier", 11, "bold"))

        for p_id, p in self.players_data.items():
            if p_id == self.my_id: continue
            x = p["x"] - cam_x
            y = p["y"] - cam_y
            if 0 <= x <= self.SCREEN_W and 0 <= y <= self.SCREEN_H:
                self.canvas.create_rectangle(x-16, y-16, x+16, y+16, fill="#b4befe", outline="#11111b", width=2)
                self.canvas.create_rectangle(x-20, y-28, x+20, y-24, fill="#585b70")
                self.canvas.create_rectangle(x-20, y-28, x-20 + (40 * (p["hp"]/p["maxHp"])), y-24, fill="#a6e3a1")
                self.canvas.create_text(x, y-38, text=p_id + " [WILD]", fill="#cdd6f4", font=("Courier", 11))

        my_sx = self.SCREEN_W // 2
        my_sy = self.SCREEN_H // 2
        self.canvas.create_rectangle(my_sx-16, my_sy-16, my_sx+16, my_sy+16, fill="#89b4fa", outline="#11111b", width=2)
        self.canvas.create_rectangle(my_sx-20, my_sy-28, my_sx+20, my_sy-24, fill="#585b70")
        if self.my_id in self.players_data:
            p_self = self.players_data[self.my_id]
            self.canvas.create_rectangle(my_sx-20, my_sy-28, my_sx-20 + (40 * (p_self["hp"]/p_self["maxHp"])), my_sy-24, fill="#a6e3a1")
        zone_lbl = " [SAFE]" if self.current_zone != "Wilderness" else " [WILD]"
        self.canvas.create_text(my_sx, my_sy-38, text=str(self.my_id) + zone_lbl, fill="#cdd6f4", font=("Courier", 11))

        self.process_visual_fx(cam_x, cam_y)
        self.render_hud()
        
        self.root.after(16, self.render_tick)

    def process_visual_fx(self, cam_x, cam_y):
        next_fx = []
        for fx in self.active_fx:
            fx["life"] -= 0.04  
            if fx["life"] <= 0: 
                continue

            if fx["type"] == "missile":
                fx["x"] += fx["vx"]
                fx["y"] += fx["vy"]
                self.canvas.create_oval(fx["x"]-10, fx["y"]-10, fx["x"]+10, fx["y"]+10, fill="#8be9fd", outline="#b4befe")
                self.canvas.create_line(fx["x"], fx["y"], fx["x"]-fx["vx"]*1.5, fx["y"]-fx["vy"]*1.5, fill="#bd93f9", width=3)
                next_fx.append(fx)

            elif fx["type"] == "cleave_arc":
                fx["radius"] += 14
                ang_spread = 1.2 * fx["life"] 
                start_a = fx["base_angle"] - ang_spread
                end_a = fx["base_angle"] + ang_spread
                
                steps = 8
                pts = []
                for s in range(steps + 1):
                    cur_a = start_a + (end_a - start_a) * (s / steps)
                    px = fx["cx"] + math.cos(cur_a) * fx["radius"]
                    py = fx["cy"] + math.sin(cur_a) * fx["radius"]
                    pts.append((px, py))
                
                for idx in range(len(pts) - 1):
                    c = "#ffb86c" if fx["life"] > 0.6 else "#ff5555"
                    self.canvas.create_line(pts[idx], pts[idx+1], fill=c, width=int(8*fx["life"]))
                next_fx.append(fx)

            elif fx["type"] == "nova_blast":
                fx["radius"] += 18
                self.canvas.create_oval(fx["cx"]-fx["radius"], fx["cy"]-fx["radius"], fx["cx"]+fx["radius"], fx["cy"]+fx["radius"], outline="#50fa7b", width=int(6*fx["life"]))
                next_fx.append(fx)

            elif fx["type"] == "floating_text":
                fx["y_off"] -= 3 
                tx = fx["wx"] - cam_x
                ty = (fx["wy"] - cam_y) + fx["y_off"]
                self.canvas.create_text(tx, ty, text=fx["text"], fill=fx["color"], font=("Courier", 16, "bold"))
                next_fx.append(fx)

        self.active_fx = next_fx

    def render_hud(self):
        # Top-left HUD box
        self.canvas.create_rectangle(20, 20, 420, 130, fill="#1e1e2e", outline="#45475a", width=2)
        self.canvas.create_text(220, 45, text=f"🌲 Area: {self.current_zone}", fill="#a6e3a1", font=("Courier", 13, "bold"))
        
        # Calculate actual gold from inventory
        gold_display = 0
        if self.my_id in self.players_data:
            for item in self.my_inventory:
                if item["name"] == "Gold Coin":
                    gold_display += item["quantity"]
            
        self.canvas.create_text(220, 75, text=f"💰 Gold: {gold_display}g", fill="#f9e2af", font=("Courier", 11, "bold"))
        self.canvas.create_text(220, 105, text="[E] Eat | [C] Gear | [B] Shop | [M] Map", fill="#f5c2e7", font=("Courier", 9))

        # Spells Bar
        now = time.time()
        aoe_cd_left = max(0.0, self.aoe_cooldown_duration - (now - self.last_aoe_cast_time))
        aoe_label = "3: Nova Burst" if aoe_cd_left <= 0 else f"CD: {aoe_cd_left:.1f}s"
        aoe_color = "#50fa7b" if aoe_cd_left <= 0 else "#6272a4"

        spells = [("1: Magic Missile", "#ff79c6"), ("2: Cleave Sweep", "#ff5555"), (aoe_label, aoe_color)]
        for i, (name, color) in enumerate(spells):
            bx = (self.SCREEN_W // 2 - 270) + (i * 190)
            by = self.SCREEN_H - 110
            self.canvas.create_rectangle(bx, by, bx+170, by+65, fill="#181825", outline=color, width=2)
            self.canvas.create_text(bx+85, by+32, text=name, fill="#cdd6f4", font=("Courier", 11, "bold"))

        # Inventory Window
        ix = self.SCREEN_W - 380
        self.canvas.create_rectangle(ix, 20, ix+360, 450, fill="#1e1e2e", outline="#45475a", width=2)
        self.canvas.create_text(ix+180, 45, text="🎒 INVENTORY MANAGER", fill="#f9e2af", font=("Courier", 13, "bold"))
        
        items_to_render = self.my_inventory[-12:] if self.my_inventory else [{"itemId": "0000", "name": "Loading matrix...", "quantity": 0}]
        for idx, item in enumerate(items_to_render):
            display_str = f"[{item['itemId']}] {item['name']} x{item['quantity']}/60"
            self.canvas.create_text(ix+20, 95 + (idx*28), text=display_str, fill="#b4befe", font=("Courier", 10), anchor="w")

        # Character Sheet Overlay (C key)
        if self.show_character_sheet and self.my_id in self.players_data:
            p_self = self.players_data[self.my_id]
            eq = p_self.get("equipment", {"weapon": None, "armor": None})
            
            cx, cy = self.SCREEN_W // 2 - 175, self.SCREEN_H // 2 - 220
            self.canvas.create_rectangle(cx, cy, cx+350, cy+440, fill="#1e1e2e", outline="#89b4fa", width=3)
            self.canvas.create_text(cx+175, cy+35, text="🛡️ CHARACTER EQUIPMENT", fill="#89b4fa", font=("Courier", 14, "bold"))
            
            # Weapon Slot
            w_name = eq["weapon"]["name"] if eq and eq.get("weapon") else "None (Base Dagger)"
            self.canvas.create_rectangle(cx+30, cy+80, cx+320, cy+150, fill="#181825", outline="#45475a", width=2)
            self.canvas.create_text(cx+175, cy+105, text=f"Weapon Slot:", fill="#cdd6f4", font=("Courier", 10, "bold"))
            self.canvas.create_text(cx+175, cy+128, text=w_name, fill="#a6e3a1", font=("Courier", 11))
            
            # Armor Slot
            a_name = eq["armor"]["name"] if eq and eq.get("armor") else "None (No Armor)"
            self.canvas.create_rectangle(cx+30, cy+170, cx+320, cy+240, fill="#181825", outline="#45475a", width=2)
            self.canvas.create_text(cx+175, cy+195, text=f"Armor Slot:", fill="#cdd6f4", font=("Courier", 10, "bold"))
            self.canvas.create_text(cx+175, cy+218, text=a_name, fill="#a6e3a1", font=("Courier", 11))
            
            self.canvas.create_text(cx+175, cy+390, text="Press [C] to close", fill="#6272a4", font=("Courier", 10))

        # Merchant Shop Overlay (B key in city)
        if self.show_merchant:
            mx, my = self.SCREEN_W // 2 - 200, self.SCREEN_H // 2 - 250
            self.canvas.create_rectangle(mx, my, mx+400, my+500, fill="#1e1e2e", outline="#f9e2af", width=3)
            self.canvas.create_text(mx+200, my+35, text="🪙 CITY MERCHANT", fill="#f9e2af", font=("Courier", 14, "bold"))
            self.canvas.create_text(mx+200, my+70, text="Buy upgrades with Gold", fill="#cdd6f4", font=("Courier", 10))
            
            # Shop items placeholder UI
            self.canvas.create_rectangle(mx+30, my+110, mx+370, my+180, fill="#181825", outline="#45475a", width=2)
            self.canvas.create_text(mx+200, my+135, text="Steel Broadsword (50g)", fill="#89b4fa", font=("Courier", 11, "bold"))
            self.canvas.create_text(mx+200, my+155, text="+15 Bonus Damage", fill="#a6e3a1", font=("Courier", 9))

            self.canvas.create_rectangle(mx+30, my+200, mx+370, my+270, fill="#181825", outline="#45475a", width=2)
            self.canvas.create_text(mx+200, my+225, text="Iron Plate Mail (75g)", fill="#89b4fa", font=("Courier", 11, "bold"))
            self.canvas.create_text(mx+200, my+245, text="Damage Reduction", fill="#a6e3a1", font=("Courier", 9))

            self.canvas.create_text(mx+200, my+450, text="Press [B] to close shop", fill="#6272a4", font=("Courier", 10))

        # Map Overlay (M key)
        if self.show_map:
            map_x, map_y = self.SCREEN_W // 2 - 200, self.SCREEN_H // 2 - 200
            self.canvas.create_rectangle(map_x, map_y, map_x+400, map_y+400, fill="#11111b", outline="#a6e3a1", width=3)
            for name, data in self.cities.items():
                cx = map_x + int((data["x"] / self.WORLD_SIZE) * 400)
                cy = map_y + int((data["y"] / self.WORLD_SIZE) * 400)
                self.canvas.create_oval(cx-6, cy-6, cx+6, cy+6, fill=data["color"])
            mpx = map_x + int((self.px / self.WORLD_SIZE) * 400)
            mpy = map_y + int((self.py / self.WORLD_SIZE) * 400)
            self.canvas.create_rectangle(mpx-4, mpy-4, mpx+4, mpy+4, fill="#89b4fa")
            
            # Top Screen Notification Banner
        if time.time() < self.notification_timer and self.notification_text:
            banner_w = 400
            bx = (self.SCREEN_W // 2) - (banner_w // 2)
            by = 20
            self.canvas.create_rectangle(bx, by, bx + banner_w, by + 50, fill="#1e1e2e", outline="#50fa7b", width=2)
            self.canvas.create_text(bx + (banner_w // 2), by + 25, text=self.notification_text, fill="#50fa7b", font=("Courier", 12, "bold"))

if __name__ == "__main__":
    window = tk.Tk()
    game = BaldursGateVibeClient(window)
    window.mainloop()
