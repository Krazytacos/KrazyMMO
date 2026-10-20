const { WebSocketServer } = require('ws');
const crypto = require('crypto');

const wss = new WebSocketServer({ port: 8080 });
const activePlayers = new Map();

const WORLD_SIZE = 4000;
const CITIES = {
    "Neon City": { x: 400, y: 400, color: "#89b4fa" },
    "Vapor Outpost": { x: 3200, y: 3200, color: "#f5c2e7" }
};

const monsters = [
    { id: "Xvart_1", x: 1200, y: 1000, hp: 60, maxHp: 60, color: "#fab387", lastAttackTime: 0 },
    { id: "Gibberling_A", x: 1500, y: 1500, hp: 40, maxHp: 40, color: "#a6e3a1", lastAttackTime: 0 },
    { id: "Ankheg_Alpha", x: 2200, y: 2500, hp: 200, maxHp: 200, color: "#f38ba8", lastAttackTime: 0 }
];

function addItemToInventory(inventory, itemName) {
    let existingSlot = inventory.find(slot => slot.name === itemName && slot.quantity < 60);
    if (existingSlot) {
        existingSlot.quantity += 1;
    } else {
        inventory.push({
            itemId: "item_" + crypto.randomBytes(3).toString('hex'),
            name: itemName,
            quantity: 1
        });
    }
}

// Background Game Simulation Loop (Runs every 50ms)
setInterval(() => {
    let now = Date.now();

    activePlayers.forEach((player) => {
        if (player.currentCity !== "Wilderness") {
            if (player.hp < player.maxHp) {
                player.hp = Math.min(player.maxHp, player.hp + 5); 
            }
        }
    });

    monsters.forEach(mob => {
        let targetPlayer = null;
        let closestDist = 600;

        activePlayers.forEach(p => {
            let dist = Math.hypot(p.x - mob.x, p.y - mob.y);
            if (dist < closestDist) {
                closestDist = dist;
                targetPlayer = p;
            }
        });

        if (targetPlayer && targetPlayer.currentCity === "Wilderness") {
            let dx = targetPlayer.x - mob.x;
            let dy = targetPlayer.y - mob.y;
            mob.x += Math.sign(dx) * 12;
            mob.y += Math.sign(dy) * 12;

            // --- 0.2 SECOND GCD ENEMY ATTACK VALIDATION ---
            if (closestDist < 40 && (now - mob.lastAttackTime >= 200)) {
                targetPlayer.hp = Math.max(0, targetPlayer.hp - 4);
                mob.lastAttackTime = now; // Lock enemy weapon slot
                if (targetPlayer.hp === 0) {
                    targetPlayer.x = 400; targetPlayer.y = 400; targetPlayer.hp = 100;
                }
            }
        } else {
            mob.x += (Math.random() - 0.5) * 20;
            mob.y += (Math.random() - 0.5) * 20;
        }
        mob.x = Math.max(100, Math.min(WORLD_SIZE - 100, mob.x));
        mob.y = Math.max(100, Math.min(WORLD_SIZE - 100, mob.y));
    });

    const packet = JSON.stringify({
        type: "update",
        players: Object.fromEntries(activePlayers),
        monsters: monsters
    });
    wss.clients.forEach(c => { if (c.readyState === 1) c.send(packet); });
}, 50);

wss.on('connection', (ws) => {
    const playerId = "Char_" + Math.random().toString(36).substr(2, 4);
    
    let startingInventory = [];
    addItemToInventory(startingInventory, "Rusty Dagger");
    addItemToInventory(startingInventory, "Dried Rations");
    addItemToInventory(startingInventory, "Gold Coin");

    activePlayers.set(playerId, {
        id: playerId, x: 400, y: 400, hp: 100, maxHp: 100,
        inventory: startingInventory, currentCity: "Neon City",
        lastCastTime: 0 // Track raw action timestamps
    });

    ws.send(JSON.stringify({ type: "welcome", id: playerId, cities: CITIES }));

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            const player = activePlayers.get(playerId);
            if (!player) return;

            if (data.type === "move") {
                player.x = data.x; player.y = data.y;
                player.currentCity = "Wilderness";
                for (const [name, coords] of Object.entries(CITIES)) {
                    if (Math.hypot(player.x - coords.x, player.y - coords.y) < 350) player.currentCity = name;
                }
            } 
            else if (data.type === "eat_item") {
                let slot = player.inventory.find(s => s.name === "Dried Rations");
                if (slot && player.hp < player.maxHp) {
                    slot.quantity -= 1;
                    player.hp = Math.min(player.maxHp, player.hp + 35); 
                    if (slot.quantity <= 0) {
                        player.inventory = player.inventory.filter(s => s.itemId !== slot.itemId);
                    }
                }
            }
else if (data.type === "buy_item") {
    if (player.currentCity !== "Wilderness") {
        let cost = data.cost;
        let goldSlot = player.inventory.find(s => s.name === "Gold Coin");
        let currentGold = goldSlot ? goldSlot.quantity : 0;
        
        if (currentGold >= cost) {
            // Deduct gold & give item
            goldSlot.quantity -= cost;
            if (goldSlot.quantity <= 0) {
                player.inventory = player.inventory.filter(s => s.itemId !== goldSlot.itemId);
            }
            addItemToInventory(player.inventory, data.itemName);
            
            // Tell the client it worked
            ws.send(JSON.stringify({
                type: "shop_response",
                success: true,
                message: `✨ Purchased ${data.itemName} for ${cost}g!`
            }));
        } else {
            // Tell the client they are broke
            ws.send(JSON.stringify({
                type: "shop_response",
                success: false,
                message: `❌ Not enough gold! You have ${currentGold}g, need ${cost}g.`
            }));
        }
    }
}
            
            else if (data.type === "cast_spell") {
                let now = Date.now();
                // --- 0.2 SECOND GCD PLAYER ACTION ENFORCEMENT ---
                if (now - player.lastCastTime < 200) return; // Silent server drop if macroing
                
                player.lastCastTime = now; // Reset global action timer slot

                activePlayers.forEach((target, targetId) => {
                    if (targetId !== playerId && player.currentCity === "Wilderness" && target.currentCity === "Wilderness") {
                        if (Math.hypot(player.x - target.x, player.y - target.y) <= data.range) {
                            target.hp = Math.max(0, target.hp - data.damage);
                        }
                    }
                });

                monsters.forEach(mob => {
                    if (Math.hypot(player.x - mob.x, player.y - mob.y) <= data.range) {
                        mob.hp = Math.max(0, mob.hp - data.damage);
                        if (mob.hp === 0) {
                            mob.x = Math.random() * (WORLD_SIZE - 400) + 200;
                            mob.y = Math.random() * (WORLD_SIZE - 400) + 200;
                            mob.hp = mob.maxHp;
                            addItemToInventory(player.inventory, (Math.random() > 0.5 ? "Dried Rations" : "Gold Coin"));
                        }
                    }
                });
            }
        } catch (e) {}
    });

    ws.on('close', () => { activePlayers.delete(playerId); });
});
