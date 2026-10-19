#!/usr/bin/env python3
"""Apply the GN1 prototype integration to a checkout of MisterTemaki/genplusgxPS5.

Usage: python3 apply_to_upstream.py /path/to/genplusgxPS5
Requires the unmodified upstream ps5 frontend near v1.7.
Does NOT overwrite the upstream remote; works in a separate working tree.
"""
import pathlib
import shutil
import sys

KIT=pathlib.Path(__file__).resolve().parent
if len(sys.argv) != 2:
    raise SystemExit('Usage: python3 apply_to_upstream.py <upstream-repo-root>')
ROOT=pathlib.Path(sys.argv[1]).resolve()
PS5=ROOT/'ps5'
if not (PS5/'frontend/fe_emu.cpp').is_file():
    raise SystemExit('Not a genplusgxPS5 checkout')

def patch(relative, replacements):
    p=ROOT/relative
    data=p.read_text()
    for old,new in replacements:
        n=data.count(old)
        if n != 1:
            raise ValueError(f'{relative}: expected anchor exactly once, found {n}: {old[:80]!r}')
        data=data.replace(old,new,1)
    p.write_text(data)
    print('patched',relative)

for f in ('fe_netplay.cpp','fe_netplay.h','fe_netplay_tls.cpp','fe_netplay_tls.h'):
    shutil.copyfile(KIT/'netplay'/f,PS5/'frontend'/f)

patch('ps5/Makefile', [
    ('VERSION ?= 1.7','VERSION ?= 1.7-netplay0.4'),
    ('TITLE_ID ?= PPSA99921','TITLE_ID ?= PPSA99931'),
    ('frontend/fe_emu.cpp frontend/fe_menu.cpp frontend/fe_settings.cpp frontend/fe_text.cpp',
     'frontend/fe_emu.cpp frontend/fe_netplay.cpp frontend/fe_netplay_tls.cpp frontend/fe_menu.cpp frontend/fe_settings.cpp frontend/fe_text.cpp'),
])
patch('ps5/Makefile', [
    ('EBOOT_OBJS = build/app/app_crt.o build/app/app_cpp_runtime.o $(PS5_CORE_OBJ) $(PS5_EMU_OBJ) $(PS5_OUT)/helper_data.o',
     'EBOOT_OBJS = build/app/app_crt.o build/app/app_cpp_runtime.o $(PS5_CORE_OBJ) $(PS5_EMU_OBJ) $(PS5_MBEDTLS_OBJ) $(PS5_OUT)/helper_data.o'),
    ('$(HOST_CXX) $(HOST_SAN) -o $@ $^ -lpthread -lm',
     '$(HOST_CXX) $(HOST_SAN) -o $@ $^ $(HOST_MBEDTLS_OBJ) -lpthread -lm'),
    ('# ---------------- PS5 ----------------',
     '# Relay uses verified TLS. Direct P2P is plaintext; development LAN/VPN only.\n'
     '%/port/frontend/fe_netplay.o: EXTRA_FLAGS = -DGENPLUS_NETPLAY_TLS\n'
     '%/port/frontend/fe_netplay_tls.o: EXTRA_FLAGS = $(MBEDTLS_FLAGS) -DCACERT_PEM=\'"$(abspath frontend/data/cacert.pem)"\' \n'
     '# ---------------- PS5 ----------------'),
])
patch('ps5/coreorbis/orbis-shims/ProsperoJailbreak.h', [
    ('constexpr int kHelperPort = 9088;', 'constexpr int kHelperPort = 19031; // netplay test build, separate from the original'),
])
patch('ps5/coreorbis/include-orbis/OrbisPaths.h', [
    ('#define ORBIS_ROOT_DEFAULT "/data/genplus"',
     '#define ORBIS_ROOT_DEFAULT "/data/genplus-netplay"'),
])
patch('ps5/frontend/fe_settings.h', [
    ('\t// library\n',
     '\t// Experimental GN1 netplay. Configure room/address via FTP in genplus-ps5.ini.\n'
     '\tint netplay_mode = 0; // off / host / join\n'
     '\tint netplay_connection_type = 0; // 0 relay TLS; 1 direct LAN/VPN; 2 auto direct-first\n'
     '\tstd::string netplay_direct_host = "127.0.0.1";\n'
     '\tint netplay_direct_port = 43378;\n'
     '\tstd::string netplay_host = "127.0.0.1";\n'
     '\tint netplay_port = 43377;\n'
     '\tstd::string netplay_room;\n'
     '\tint netplay_delay = 6;\n'
     '\t// library\n'),
])
patch('ps5/frontend/fe_settings.cpp', [
    ('\t\telse if (key == "last_rom")\n',
     '\t\telse if (key == "netplay_mode")\n\t\t\tnetplay_mode = Clamp(n, 0, 2);\n'
     '\t\telse if (key == "netplay_connection_type")\n\t\t\tnetplay_connection_type = Clamp(n, 0, 2);\n'
     '\t\telse if (key == "netplay_direct_host")\n\t\t\tnetplay_direct_host = val;\n'
     '\t\telse if (key == "netplay_direct_port")\n\t\t\tnetplay_direct_port = Clamp(n, 1, 65535);\n'
     '\t\telse if (key == "netplay_host")\n\t\t\tnetplay_host = val;\n'
     '\t\telse if (key == "netplay_port")\n\t\t\tnetplay_port = Clamp(n, 1, 65535);\n'
     '\t\telse if (key == "netplay_room")\n\t\t\tnetplay_room = val;\n'
     '\t\telse if (key == "netplay_delay")\n\t\t\tnetplay_delay = Clamp(n, 1, 15);\n'
     '\t\telse if (key == "last_rom")\n'),
    ('\tfprintf(f, "last_rom=%s\\n", last_rom.c_str());',
     '\tfprintf(f, "netplay_mode=%d\\n", netplay_mode);\n'
     '\tfprintf(f, "netplay_connection_type=%d\\n", netplay_connection_type);\n'
     '\tfprintf(f, "netplay_direct_host=%s\\n", netplay_direct_host.c_str());\n'
     '\tfprintf(f, "netplay_direct_port=%d\\n", netplay_direct_port);\n'
     '\tfprintf(f, "netplay_host=%s\\n", netplay_host.c_str());\n'
     '\tfprintf(f, "netplay_port=%d\\n", netplay_port);\n'
     '\tfprintf(f, "netplay_room=%s\\n", netplay_room.c_str());\n'
     '\tfprintf(f, "netplay_delay=%d\\n", netplay_delay);\n'
     '\tfprintf(f, "last_rom=%s\\n", last_rom.c_str());'),
])
patch('ps5/frontend/fe_menu.cpp', [
    ('\tS_UPDATES,\n\tS_COUNT', '\tS_UPDATES,\n\tH_NETPLAY,\n\tS_NETPLAY_MODE,\n\tS_NETPLAY_CONNECTION_TYPE,\n\tS_NETPLAY_ROOM,\n\tS_NETPLAY_RELAY,\n\tS_NETPLAY_DIRECT_HOST,\n\tS_NETPLAY_DIRECT_PORT,\n\tS_COUNT'),
    ('\t\tcase H_LIBRARY: return {"LIBRARY", "", true, true};',
     '\t\tcase H_NETPLAY: return {"NETPLAY (TEST BUILD)", "", true, true};\n'
     '\t\tcase S_NETPLAY_MODE: return {"Online play", c.netplay_mode == 1 ? "Host" : c.netplay_mode == 2 ? "Join" : "Off"};\n'
     '\t\tcase S_NETPLAY_CONNECTION_TYPE: return {"Connection type", c.netplay_connection_type == 0 ? "Relay (TLS)" : c.netplay_connection_type == 1 ? "Direct P2P (test)" : "Automatic (test)"};\n'
     '\t\tcase S_NETPLAY_ROOM: return {"Room code (Cross to edit)", NetplayPreview(c.netplay_room)};\n'
     '\t\tcase S_NETPLAY_RELAY: return {"Relay host (Cross to edit)", NetplayPreview(c.netplay_host), c.netplay_connection_type != 1};\n'
     '\t\tcase S_NETPLAY_DIRECT_HOST: return {"Direct host (Cross to edit)", NetplayPreview(c.netplay_direct_host), c.netplay_connection_type != 0};\n'
     '\t\tcase S_NETPLAY_DIRECT_PORT: snprintf(buf, sizeof(buf), "%d", c.netplay_direct_port); return {"Direct TCP port", buf, c.netplay_connection_type != 0};\n'
     '\t\tcase H_LIBRARY: return {"LIBRARY", "", true, true};'),
    ('\t\tcase S_COVERS: c.covers_download = !c.covers_download; break;',
     '\t\tcase S_NETPLAY_MODE: c.netplay_mode = Cycle(c.netplay_mode, dir, 3); break;\n'
     '\t\tcase S_NETPLAY_CONNECTION_TYPE: c.netplay_connection_type = Cycle(c.netplay_connection_type, dir, 3); break;\n'
     '\t\tcase S_NETPLAY_DIRECT_PORT: c.netplay_direct_port = std::max(1024, std::min(65535, c.netplay_direct_port + dir)); break;\n'
     '\t\tcase S_COVERS: c.covers_download = !c.covers_download; break;'),
])
# Prevent the prototype helper from ever updating itself from the unmodified
# upstream repository; the release identifiers belong to a different title.
patch('ps5/frontend/fe_menu.cpp', [
    ('std::string UpdateValue()\n{',
     'std::string UpdateValue()\n{\n    return "Disabled for netplay test build";'),
    ('void UpdateAction()\n{',
     'void UpdateAction()\n{\n    return; // Never install official emulator updates into this development title.'),
])

# Controller-operated netplay field editor: eliminates FTP as a prerequisite for
# initial setup. Uses the frontend's existing gamepad reader/drawing primitives.
patch('ps5/frontend/fe_menu.cpp', [
        ('Row SettingRowFor(int s)\n{', 'std::string NetplayPreview(const std::string& text);\n\nRow SettingRowFor(int s)\n{'),
    ('void SettingsScreen(bool over_game)\n{',
     '''// Compact controller keyboard; local configuration, no network text input.
std::string NetplayPreview(const std::string& text)
{
    if (text.empty()) return "Not set";
    return text.size() <= 23 ? text : text.substr(0, 20) + "...";
}

bool EditNetplayField(const char* title, std::string& value, bool room)
{
    const std::string alphabet =
        room ? "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" :
               "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-";
    const int columns = 10;
    const int key_count = int(alphabet.size()) + 2; // Delete, Done
    const size_t max_len = room ? 32 : 120;
    std::string entered = value;
    int selected = 0;
    NavReader nav;
    for (;;)
    {
        Header(title);
        ps5video::FillRect(160, 225, W - 320, 80, kPanel);
        DrawText(185, 244, FitText(entered.empty() ? std::string("(empty)") : entered, 3, W - 400).c_str(),
                 3, entered.empty() ? kDim : kText);
        for (int i = 0; i < key_count; ++i)
        {
            const int x = 290 + (i % columns) * 135;
            const int y = 345 + (i / columns) * 66;
            const bool active = selected == i;
            ps5video::FillRect(x, y, 125, 56, active ? kSel : kPanel);
            std::string label;
            if (i == int(alphabet.size())) label = "DEL";
            else if (i == int(alphabet.size()) + 1) label = "DONE";
            else label = std::string(1, alphabet[size_t(i)]);
            DrawText(x + (125 - TextWidth(label.c_str(), 3)) / 2, y + 9, label.c_str(), 3,
                     active ? kText : kAccent);
        }
        Footer(std::string(icon::Cross) + " Add/Done    " + icon::Circle +
               " Delete    OPTIONS Save    L3+R3 Cancel");
        Present();
        const Nav n = nav.Read();
        if (n.left) selected = (selected + key_count - 1) % key_count;
        if (n.right) selected = (selected + 1) % key_count;
        if (n.up && selected >= columns) selected -= columns;
        if (n.down && selected + columns < key_count) selected += columns;
        if (n.back && !entered.empty()) entered.pop_back();
        if (n.menu) return false; // cancel, do not overwrite
        if (n.options)
        {
            value = entered;
            return true;
        }
        if (n.ok)
        {
            if (selected < int(alphabet.size()))
            {
                if (entered.size() < max_len) entered.push_back(alphabet[size_t(selected)]);
            }
            else if (selected == int(alphabet.size()))
            {
                if (!entered.empty()) entered.pop_back();
            }
            else
            {
                value = entered;
                return true;
            }
        }
    }
}

void SettingsScreen(bool over_game)
{'''),
    ('\t\telse if (sel < S_COUNT && (n.left || n.right || n.ok))\n\t\t\tChangeSetting(sel, n.left ? -1 : 1);',
     '''        else if (n.ok && (sel == S_NETPLAY_ROOM || sel == S_NETPLAY_RELAY || sel == S_NETPLAY_DIRECT_HOST))
        {
            Settings& c = Config();
            std::string& target = sel == S_NETPLAY_ROOM ? c.netplay_room :
                (sel == S_NETPLAY_RELAY ? c.netplay_host : c.netplay_direct_host);
            const char* title = sel == S_NETPLAY_ROOM ? "Netplay room code" :
                (sel == S_NETPLAY_RELAY ? "TLS relay DNS hostname" : "Direct host IPv4 / hostname");
            if (EditNetplayField(title, target, sel == S_NETPLAY_ROOM))
                c.Save();
            nav = NavReader(); // reset input repeat after returning from keyboard
        }
        else if (sel < S_COUNT && (n.left || n.right || n.ok))
            ChangeSetting(sel, n.left ? -1 : 1);'''),
])

patch('ps5/frontend/fe_emu.h', [
    ('bool GameLoaded();', 'bool GameLoaded();\n// GN1 prototype: call after loading the ROM, before the first emulated frame.\nbool NetplayBegin(std::string* error);'),
])
patch('ps5/frontend/fe_emu.cpp', [
    ('#include "fe_emu.h"', '#include "fe_emu.h"\n#include "fe_netplay.h"'),
    ('\tuint32_t prev_p1 = 0;\n',
     '\tuint32_t prev_p1 = 0;\n\tuint16_t net_host = 0, net_join = 0;\n'),
    ('\tif (port >= unsigned(ps5input::kMaxPads) || (device & RETRO_DEVICE_MASK) != RETRO_DEVICE_JOYPAD || index != 0)\n\t\treturn 0;\n',
     '\tif (port >= unsigned(ps5input::kMaxPads) || (device & RETRO_DEVICE_MASK) != RETRO_DEVICE_JOYPAD || index != 0)\n\t\treturn 0;\n'
     '\tif (netplay::Active())\n\t{\n'
     '\t\tconst uint16_t bits = port == 0 ? g.net_host : (port == 1 ? g.net_join : 0);\n'
     '\t\tif (id == RETRO_DEVICE_ID_JOYPAD_MASK) return int16_t(bits);\n'
     '\t\treturn id < 16 ? int16_t((bits >> id) & 1) : 0;\n\t}\n'),
    ('void CloseGame()\n{\n\tif (!g.loaded)',
     'void CloseGame()\n{\n\tnetplay::Stop();\n\tif (!g.loaded)'),
    ('bool GameLoaded()\n{',
     '''// Fingerprint exactly the bytes provided for a ROM; FNV64 is for mismatch detection,
// not for security. This early prototype supports only identical cartridge files.
namespace {
uint64_t HashBytes(uint64_t h, const void* data, size_t size) {
    const auto* p = static_cast<const uint8_t*>(data);
    for (size_t i = 0; i < size; ++i) h = (h ^ p[i]) * 1099511628211ull;
    return h;
}
uint64_t RomHash() {
    uint64_t h = 14695981039346656037ull;
    // ZIP game contents, or the original cartridge bytes.
    if (!g.rom.empty()) return HashBytes(h, g.rom.data(), g.rom.size());
    FILE* f = fopen(g.path.c_str(), "rb");
    if (!f) return 0;
    uint8_t buf[32768]; size_t n = 0, total = 0;
    while ((n = fread(buf, 1, sizeof(buf), f)) != 0) {
        total += n;
        if (total > 64u * 1024u * 1024u) { fclose(f); return 0; }
        h = HashBytes(h, buf, n);
    }
    const bool good = !ferror(f) && total != 0;
    fclose(f);
    return good ? h : 0;
}
uint64_t SettingsHash() {
    const fe::Settings& c = fe::Config();
    char buf[256];
    snprintf(buf, sizeof(buf), "GN1:" GENPLUS_CORE_VERSION ":" GENPLUS_PS5_VERSION ":%d:%d:%d:%d:%d:%d:%d",
        c.region, c.no_sprite_limit ? 1 : 0, c.fm_chip, c.pad_type, c.multitap, c.lowpass ? 1 : 0, c.netplay_delay);
    return HashBytes(14695981039346656037ull, buf, strlen(buf));
}
} // namespace

bool NetplayBegin(std::string* error) {
    const fe::Settings& c = fe::Config();
    if (c.netplay_mode == 0) return true;
    if (!g.loaded || g.system != fe::System::Md) {
        if (error) *error = "Netplay test supports Mega Drive / Genesis cartridges only.";
        return false;
    }
    const uint64_t hash = RomHash();
    if (!hash) {
        if (error) *error = "Could not hash ROM for online session.";
        return false;
    }
    netplay::Config n;
    n.mode = c.netplay_mode; n.connection_type = c.netplay_connection_type;
    n.host = n.connection_type == 0 ? c.netplay_host : c.netplay_direct_host;
    n.port = n.connection_type == 0 ? c.netplay_port : c.netplay_direct_port;
    n.fallback_host = c.netplay_host; n.fallback_port = c.netplay_port;
    n.room = c.netplay_room; n.delay = c.netplay_delay;
    std::string why;
    OrbisLog("[netplay] %s via %s", n.mode == 1 ? "host" : "join", n.connection_type == 0 ? "TLS relay" : n.connection_type == 1 ? "direct P2P" : "automatic direct/relay");
    ProsperoNotify("Genesis Plus GX Netplay: waiting for second player (up to 120 s)");
    const bool ok = netplay::Start(n, hash, SettingsHash(), why);
    if (!ok) {
        OrbisLog("[netplay] %s", why.c_str());
        if (error) *error = why;
    } else {
        OrbisLog("[netplay] connected via %s; beginning synchronized frames", netplay::TransportName());
        ProsperoNotify("Genesis Plus GX Netplay: both players connected");
    }
    return ok;
}

bool GameLoaded()\n{'''),
    ('\tif (!g.loaded)\n\t\treturn false;\n\tconst size_t size = retro_serialize_size();',
     '\tif (!g.loaded || netplay::Active())\n\t\treturn false;\n\tconst size_t size = retro_serialize_size();'),
    ('bool LoadState(int slot)\n{\n\tif (!g.loaded)',
     'bool LoadState(int slot)\n{\n\tif (!g.loaded || netplay::Active())'),
    ('\tif (l2 && !r2)\n\t{', '\tif (l2 && !r2 && !netplay::Active())\n\t{'),
    ('\tconst bool want_rewind = cfg.rewind && l2 && r2;',
     '\tconst bool want_rewind = !netplay::Active() && cfg.rewind && l2 && r2;'),
    ('\tconst bool want_turbo = r2 && !l2;',
     '\tconst bool want_turbo = !netplay::Active() && r2 && !l2;'),
    ('\t// -- emulate\n\tGENPLUS_STAGE(Emu, "retro_run");',
     '''\t// -- GN1 synchronized input pair for the current frame.
    if (netplay::Active()) {
        std::string why;
        // Always read the local PS5's first pad. The host becomes emulated port 0;
        // joiner becomes emulated port 1. Both devices run both players locally.
        const uint16_t local = g.wait_release ? 0 : RetroPadBits(ps5input::Snapshot(0), false);
        uint64_t digest = 0;
        // Compare serialized core states every 120 frames. Detect divergent save RAM,
        // different emulator behavior, or settings that escaped the handshake.
        if (g.frames % 120 == 0) {
            const size_t n = retro_serialize_size();
            if (n == 0 || n > 64u * 1024u * 1024u) {
                why = "core does not support safe state hashing";
                netplay::Stop(); Osd(why); return FrameResult::OpenMenu;
            }
            std::vector<uint8_t> state(n);
            if (!retro_serialize(state.data(), n)) {
                why = "failed to sample emulator state";
                netplay::Stop(); Osd(why); return FrameResult::OpenMenu;
            }
            digest = HashBytes(14695981039346656037ull, state.data(), n);
        }
        if (!netplay::Step(g.frames, local, digest, g.net_host, g.net_join, why)) {
            OrbisLog("[netplay] disconnected: %s", why.c_str());
            Osd("Netplay disconnected: " + why);
            return FrameResult::OpenMenu;
        }
    }
\t// -- emulate\n\tGENPLUS_STAGE(Emu, "retro_run");'''),
    ('\tif ((raw & menu_combo) == menu_combo && (pressed & menu_combo))\n\t\treturn FrameResult::OpenMenu;',
     '\tif ((raw & menu_combo) == menu_combo && (pressed & menu_combo))\n\t{\n\t\tnetplay::Stop(); // multiplayer session ends before the local pause menu\n\t\treturn FrameResult::OpenMenu;\n\t}'),
])
patch('ps5/coreorbis/main-boot.cpp', [
    ('\tconst double quit_at = from_command_line && QuitAfter() > 0 ? Now() + QuitAfter() : 0;',
     '''\tstd::string netplay_error;
    if (!emu::NetplayBegin(&netplay_error)) {
        fe::MessageBox("Netplay session failed", netplay_error);
        emu::CloseGame();
        return !from_command_line;
    }
\tconst double quit_at = from_command_line && QuitAfter() > 0 ? Now() + QuitAfter() : 0;'''),
    ('void AutoCheckUpdates()\n{', 'void AutoCheckUpdates()\n{\n    return; // Disable upstream auto-updates for this test build.'),
])
print('GN1 changes staged. Build from upstream/ps5 using the usual PS5 SDK: make ps5')
