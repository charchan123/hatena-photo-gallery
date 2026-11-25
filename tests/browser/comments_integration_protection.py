"""Read-only integration gate: latest main plus exact, reviewed PR 137 bytes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PR137 = '1766b1693ec87a2945b98abc5456f48fc9a13026'
PR135 = '090eac16c25129695452a10a076532c752d8bd27'
REVIEWED = {'.gitignore', 'admin/comments_client.py', 'comments/worker.mjs',
            'comments/package.json', 'comments/package-lock.json'}
CPU_BASE = '582a6c19e136fe5f7f6b2c2448cb0f63f14d1235'
CPU_RUNTIME = {'comments/staging/worker.mjs', 'comments/staging/registry.mjs'}
RELEASE_MAIN = '249bf1845bdd5d3c7a46e7939f0cd54b6eef9792'
RELEASE_FILES = {
    'admin/comments_client.py', 'assets/research-comments.js', 'comments/worker.mjs',
    'requirements.txt', 'research_comments.py', 'research_ui.py', 'comments/tests/api.test.mjs',
}
LINE_MAIN = 'f19541524a989f2ab1979c78a9bff5e5e0274092'
LINE_FILES = {'assets/research-comments.js', 'comments/worker.mjs',
              'comments/wrangler.jsonc', 'research_comments.py'}
LINE_NEW = {'comments/line/0001_outbox.sql', 'comments/line/notify.mjs'}
ACTIVITY_FILES = {'assets/research-comments.js',
                  'comments/worker.mjs', 'comments/tests/api.test.mjs', 'research_ui.py'}
ACTIVITY_MAIN = 'dcd8d072bffa23495f7a1028a4636f3eb1f7ca70'
POST_RECOVERY_MAIN = '5dc43d89b2d8b05afd3985b3d6515c8b7f8de48b'
POST_RECOVERY_FILES = {'assets/research-comments.js', 'comments/worker.mjs', 'comments/tests/api.test.mjs'}
# Independent Best Shot design PR. No comment/Worker file is exempted.
EXHIBITION_BASE = '90fbdeb761abe217db7179e87d0fcf13a44b2b0b'
EXHIBITION_MODIFIED = {'best_shot_ui.py', 'assets/best-shots.css'}
EXHIBITION_NEW = {'assets/best-shot-exhibition.js', 'previews/best-shot-exhibition-20261121.html'}
# Only PR #164's reviewed reader-copy and layout bytes are permitted against
# the frozen pre-copy main. Other protection gates and worker pins are unchanged.
COPY_AUDIT_BASE = 'f791217b192c561a16541be2211758b8ec6ab3d0'
COPY_AUDIT_BLOBS = {
    'main.py': '0ff665f1a7b3cd07ffc25f1ab95f074c0331f478',
    'assets/portal.css': '2d1c41bc5cabfa582aeea7b8e87532c2dedd4e50',
    'assets/research.css': 'b1926a5a16310698377656dfe449e7a39052b8a3',
    'assets/research-comments.js': 'e770b36cadf9ec4f640821d2eb6f4bbb2898a5fe',
    'best_shot_ui.py': '96b7569629bc524a055371fb096fc710065cee4a',
    'detail_ui.py': '85e630501fd622aaafd4a634944498600581f42c',
    'feature_ui.py': 'b7d14185b59a3bb1aae7d90565076726b2ae57cd',
    'records_ui.py': 'cfc82d0a8d22245bfec4cbe66a10de259e3a53c4',
    'research_ui.py': '0eae86e8d2b484b0cb0280cb883796449791cf6b',
    'season_ui.py': '2b5c6465557cb25873ef8b98360a8df2ce30098a',
}
# Follow-up to PR #164: precisely two user-approved portal-source blobs.
# The reviewed base must be the merged PR #164 main, never an arbitrary PR.
PORTAL_FOLLOWUP_BASE = 'd9acaed996ad7bb137e7d28c9c1bdcc77ffac37e'
PORTAL_FOLLOWUP_BLOBS = {
    'main.py': '6ab3f79a1be3cc55ddcaffe4f6381608458f1715',
    'assets/portal.css': '96653f6d85a36ec34db342311bf7d3545bfde761',
}
# This follow-up adjusts only the 3 portal guide cards; keep source checks exact.
RIGHT_NOTE_MAIN = '2af083e7ddf47eb8e374f38b2244e2f71a1729ed'
RIGHT_NOTE_CSS_BLOB = 'd5796f19276dbe6ead3f4d8afddf1ad37b72d07f'
RIGHT_ANCHOR_MAIN = '8971cbb5b9250733270853be50de48a6eec2de9c'
RIGHT_ANCHOR_CSS_BLOB = 'fa4e0476c1e5c18374b310a505a50aed06ab046a'
# Four existing, exact-name subject links. Never authorize classification or source edits.
EXISTING_FOUR_LINK_BASE = '7da1d3e27d351b18ca8c6bc0f25bb3d73f7f7cf3'
# The shared LightGallery historical reviewer uses this older main, whose
# taxonomy differs from the reviewed PR #168 only by these same four links.
HISTORICAL_GALLERY_BASE = '8007a72708aff2dfa14e2e9638f44720bb449b76'
EXISTING_FOUR_LINKS = {
    'ヤマドリタケモドキ': 'yamadoritakemodoki',
    'シイタケ': 'shiitake',
    'ベニテングタケ': 'benitengutake',
    'ドクヤマドリ': 'dokuyamadori',
}
# Copy-only change based on the immutable, reviewed PR #168 main.
# Only the exact approved two source blobs are allowed to differ.
DETAIL_COPY_BASE = 'f41901f452ef0046d8012355236c0dff82e587dc'
DETAIL_COPY_BLOBS = {
    'main.py': '82c60ac39243c22e18b65f90c81273bf27d59e8f',
    'detail_ui.py': 'df4751111a023756bf05c0d59b5df748c5326fe8',
}
# Future and existing published detail pages are regenerated from one reviewed
# presentation-only module. Data masters and comments remain byte-protected.
FOOD_NOTE_COPY_BASE = 'a580a7dd9913645efc290cd9235ea7f994386b8b'
FOOD_NOTE_COPY_BLOBS = {
    'detail_ui.py': '3fe6f66947dfe1d83a99fc7fcca2179e0c606a6e',
}
# 51 reviewed source notes, exact user-facing renderer blob only.
POLITE_51_BASE = '3af0f671a610224c32e61fc1836d895d80c35409'
POLITE_51_BLOBS = {
    'detail_ui.py': 'bac9e7d01f4575fe70a8f3b491def105e9af805e',
}
# Four exact new display links based on current published baseline. Keep other
# protected sources immutable and pin all three modified Python Git blobs.
NEXT_FOUR_LINK_BASE = 'b01b0cbe66afc2ab30bc4ca08d8c9f845fcb868f'
NEXT_FOUR_LINK_BLOBS = {
    'main.py': 'be519f9cc62dcb23ea3766270f40acfcf5960a2a',
    'portal_data.py': '197f501b4d669e9d72688e83267e3644c4f50978',
    'detail_ui.py': 'd58b5f5bc09d2820c908eb57e89fb3aed03299c7',
}
# Next group: only the exact reader-facing note render helper may change.
THIRD_FOUR_LINK_BASE = '7b7f27fd2acc46f92d672320ac680fad4bb237a0'
THIRD_FOUR_LINK_BLOBS = {
    'detail_ui.py': '216984bd6d0c017bb21e6c3874765a5b9397af6b',
    'data/guide-links.json': '772398ae86b28e8f9b78d0846d7eac06277261f5',
}
# Fourth group: the new source note renderer and the exact twelve-entry
# manifest are the only two protected exceptions for this immutable base.
FOURTH_FOUR_LINK_BASE = 'ee64c84509c1115252000a9828fa207c2095cb9b'
FOURTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': '00642a105bc74a1229d82838b1b7acc4f0d5344b',
    'data/guide-links.json': '21489ddcf589456f3a0b564e9ace78b55488f1d0',
}
# Fifth group: only these two exact, human-reviewed Git blobs may differ.
FIFTH_FOUR_LINK_BASE = '2ff647f08f488bb439a6d601ec38efd55924a783'
FIFTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': '7c7fa7c2aa44d0e75136b7c62baa6281b44572b4',
    'data/guide-links.json': 'f0a01bc2dd77bcde1d397b29898c4a59304b822e',
}
# Sixth group: two precisely reviewed source blobs against immutable fifth-group main.
SIXTH_FOUR_LINK_BASE = '019b734725471dba35641b188b30eb0d12e384de'
SIXTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': '4706e139648691fa163f6b2282944bd7f858c8b2',
    'data/guide-links.json': '4b0230719deed0f5f86d17ba960d23eda594ebc3',
}
# Seventh group: protect exactly these two source blobs against PR #176 main.
SEVENTH_FOUR_LINK_BASE = '8de52dfcc1c4d5756ea6e7a87b4fc150df2cdb1f'
SEVENTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': '2b856a1190264c6ba2077f3fbff1c8b817a0f27b',
    'data/guide-links.json': 'e0dd8f241c9114bc99a702336685920bc1e84426',
}
# Eighth group: only exact source blobs reviewed against the #177 main.
EIGHTH_FOUR_LINK_BASE = '27be968fb371d6e7f0a552abe860ec203af04954'
EIGHTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': '09c09d37d658a95bb4b39aaa5a682217b300200b',
    'data/guide-links.json': 'ff00d8d4d03ff829d81e74b4074a87450b8a9a3e',
}
# Ninth group: these two reviewed Git blobs only, against #178 merged main.
NINTH_FOUR_LINK_BASE = 'a27c4e9b3f3b11538c93e4162d383e7a902d5b4e'
NINTH_FOUR_LINK_BLOBS = {
    'detail_ui.py': 'ac815d2705eefac0fdb8e93e785969ccd12f7261',
    'data/guide-links.json': '3eea9ce11b42c8b83ea48a9eae4be1e6cd3bce79',
}
# Tenth group: allow only two exact source blob edits against merged ninth group.
TENTH_TWO_LINK_BASE = 'e4209e784440e13ed6c97adbf62ded256447a108'
TENTH_TWO_LINK_BLOBS = {
    'detail_ui.py': 'c731a249807f30e473ae3a1d74ed31163bd20dca',
    'data/guide-links.json': '417d716ac932c1c71aa5608e968067adb8cd93c1',
}
# Guide audit changes only the exact presentation module and adds a
# separate display data file. Keep all comment and legacy source byte checks.
GUIDE_ENRICHMENT_BASE = '1c9f76847e6ebd4c28e0c3a2c2a2b22e7b78018a'
GUIDE_ENRICHMENT_BLOBS = {
    'detail_ui.py': '8d522a7c9c299ceacdb22d41bf0d2edd8d23cd18',
    'data/taxonomy-display-ja.json': '6d4d6b85d262470a0d49de4d783c8e5399f1255c',
}
GUIDE_DISPLAY_BASE = '1cf063ae2f969c0eb58820c61a1c51c5eea06528'
GUIDE_DISPLAY_BLOB = '2148844d8a3366760dbe2f398608d0d696b9aa35'
GUIDE_DISPLAY_DATA = 'data/taxonomy-display-ja.json'
GUIDE_DISPLAY_DATA_BLOB = 'b1e84cbc158924218cfe968f3b3b9af9217230ef'
PUBLIC_CONFIG = 'comments/public-config.json'
PRODUCTION_ORIGIN = 'https://kinoko-research-comments.sasama-bb.workers.dev'
RELEASE_ID = 'research-comments-production-20261120'
DISABLED_CONFIG = {'version': 1, 'enabled': False, 'api_url': '', 'turnstile_site_key': '', 'release_approval': None}

def assert_staging_source(path, content):
    """Only the two explicitly reviewed CPU runtime files may differ in Nov 1.

    Preserve all old frozen checks; use exact SHA pins for the intended update,
    rather than exempting the entire staging directory from byte protection.
    """
    if path not in CPU_RUNTIME:
        assert content == git('show', f'{PR137}:{path}'), path
        return
    pins = json.loads((ROOT/'audit/comments-cpu-options-20261101/runtime-hashes.json').read_text(encoding='utf-8'))
    assert pins['baseline'] == CPU_BASE and set(pins['files']) == CPU_RUNTIME
    assert hashlib.sha256(content).hexdigest() == pins['files'][path], path

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def assert_reviewed_source(base, path, current):
    """Never hide a main change behind the old PR's allowance."""
    original = git('show', f'{base}:{path}')
    if current == original:
        return
    if path in GUIDE_ENRICHMENT_BLOBS and git('rev-parse', base).decode().strip() == GUIDE_ENRICHMENT_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == GUIDE_ENRICHMENT_BLOBS[path], path
        return
    if path == 'detail_ui.py' and git('rev-parse', base).decode().strip() == GUIDE_DISPLAY_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == GUIDE_DISPLAY_BLOB, path
        return
    if path in TENTH_TWO_LINK_BLOBS and git('rev-parse', base).decode().strip() == TENTH_TWO_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == TENTH_TWO_LINK_BLOBS[path], path
        return
    if path in NINTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == NINTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == NINTH_FOUR_LINK_BLOBS[path], path
        return
    if path in EIGHTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == EIGHTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == EIGHTH_FOUR_LINK_BLOBS[path], path
        return
    if path in SEVENTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == SEVENTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == SEVENTH_FOUR_LINK_BLOBS[path], path
        return
    if path in SIXTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == SIXTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == SIXTH_FOUR_LINK_BLOBS[path], path
        return
    if path in FIFTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == FIFTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == FIFTH_FOUR_LINK_BLOBS[path], path
        return
    if path in FOURTH_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == FOURTH_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == FOURTH_FOUR_LINK_BLOBS[path], path
        return
    if path in THIRD_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == THIRD_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == THIRD_FOUR_LINK_BLOBS[path], path
        return
    if path in NEXT_FOUR_LINK_BLOBS and git('rev-parse', base).decode().strip() == NEXT_FOUR_LINK_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == NEXT_FOUR_LINK_BLOBS[path], path
        return
    if path in POLITE_51_BLOBS and git('rev-parse', base).decode().strip() == POLITE_51_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == POLITE_51_BLOBS[path], path
        return
    if path in FOOD_NOTE_COPY_BLOBS and git('rev-parse', base).decode().strip() == FOOD_NOTE_COPY_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == FOOD_NOTE_COPY_BLOBS[path], path
        return
    if path in DETAIL_COPY_BLOBS and git('rev-parse', base).decode().strip() == DETAIL_COPY_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == DETAIL_COPY_BLOBS[path], path
        return
    if path == 'data/subject-taxonomy.json' and git('rev-parse', base).decode().strip() in {EXISTING_FOUR_LINK_BASE, HISTORICAL_GALLERY_BASE}:
        expected = json.loads(original)
        linked = set()
        for entry in expected['entries']:
            name = entry['canonical_name']
            if name in EXISTING_FOUR_LINKS:
                assert entry['subject_type'] == 'mushroom' and 'mushroom_master_id' not in entry, name
                entry['mushroom_master_id'] = EXISTING_FOUR_LINKS[name]
                linked.add(name)
        assert linked == EXISTING_FOUR_LINKS.keys(), path
        assert current == (json.dumps(expected, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), path
        return
    if path in COPY_AUDIT_BLOBS and git('rev-parse', base).decode().strip() == COPY_AUDIT_BASE:
        # Hash the exact Git blob bytes. Never exempt a whole directory or
        # relax the existing reviewed Worker/comment/source protections.
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == COPY_AUDIT_BLOBS[path], path
        return
    if path in PORTAL_FOLLOWUP_BLOBS and git('rev-parse', base).decode().strip() == PORTAL_FOLLOWUP_BASE:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == PORTAL_FOLLOWUP_BLOBS[path], path
        return
    if path == 'assets/portal.css' and git('rev-parse', base).decode().strip() == RIGHT_ANCHOR_MAIN:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == RIGHT_ANCHOR_CSS_BLOB, path
        return
    if path == 'assets/portal.css' and git('rev-parse', base).decode().strip() == RIGHT_NOTE_MAIN:
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == RIGHT_NOTE_CSS_BLOB, path
        return
    if path in LINE_FILES:
        pins = line_pins()
        if hashlib.sha256(current).hexdigest() == pins[path]:
            assert original == git('show', f'{LINE_MAIN}:{path}'), f'LINE main advanced: {path}'
            return
    if path in EXHIBITION_MODIFIED:
        # Exception only for this Best Shot draft's exact Git blobs.
        # The baseline must be unchanged and all non-Best-Shot sources stay pinned.
        pins = json.loads((ROOT/'audit/best-shot-exhibition-20261121/files.json').read_text(encoding='utf-8'))
        assert pins['base_main'] == EXHIBITION_BASE
        assert set(pins['files']) == EXHIBITION_MODIFIED | EXHIBITION_NEW
        assert original == git('show', f'{EXHIBITION_BASE}:{path}'), f'Best Shot main advanced: {path}'
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == pins['files'][path], path
        return
    if path in POST_RECOVERY_FILES:
        pins = json.loads((ROOT/'audit/comments-post-recovery-20261120/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == POST_RECOVERY_MAIN and set(pins['files']) == POST_RECOVERY_FILES
        if hashlib.sha256(current).hexdigest() == pins['files'][path]:
            assert_reviewed_source(base, path, git('show', f'{POST_RECOVERY_MAIN}:{path}'))
            return
    if path == PUBLIC_CONFIG:
        config = json.loads(current)
        assert json.loads(original) == DISABLED_CONFIG or config == DISABLED_CONFIG
        if config != DISABLED_CONFIG:
            assert config == {'version': 1, 'enabled': True, 'api_url': PRODUCTION_ORIGIN,
                              'turnstile_site_key': config['turnstile_site_key'], 'release_approval': RELEASE_ID}
            assert re.fullmatch(r'0x[A-Za-z0-9_-]{12,100}', config['turnstile_site_key'])
        return
    if path in ACTIVITY_FILES:
        pins = json.loads((ROOT/'audit/comments-activity-20261118/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == ACTIVITY_MAIN and set(pins['files']) == ACTIVITY_FILES
        assert original == git('show', f'{ACTIVITY_MAIN}:{path}'), f'main advanced: {path}'
        if hashlib.sha256(current).hexdigest() == pins['files'][path]:
            return
    if path in RELEASE_FILES:
        # Keep the original reviewed PR bytes acceptable and pin the new release
        # delta. Never accept a changed version of the same file from main.
        baseline = git('show', f'{RELEASE_MAIN}:{path}')
        assert original == baseline, f'main advanced: {path}'
        if path in REVIEWED and current == git('show', f'{PR137}:{path}'):
            return
        pins = json.loads((ROOT/'audit/comments-release-prep-20261117/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == RELEASE_MAIN and set(pins['files']) == RELEASE_FILES
        assert hashlib.sha256(current).hexdigest() == pins['files'][path], path
        return
    assert path in REVIEWED, path
    # package*.json are newly added in PR137, so not reached by a main file loop.
    assert original == git('show', f'{PR135}:{path}'), f'main advanced: {path}'
    assert current == git('show', f'{PR137}:{path}'), f'PR137 changed: {path}'

def line_pins():
    pins = json.loads((ROOT/'audit/comments-line-20261118/files.json').read_text(encoding='utf-8'))
    assert pins['main'] == LINE_MAIN and set(pins['files']) == LINE_FILES | LINE_NEW
    return pins['files']

def collect(base='origin/main'):
    git('merge-base', '--is-ancestor', base, 'HEAD')
    protected = [p for p in git('ls-tree', '-rz', '--name-only', base).decode().split('\0')
                 if p and not p.startswith(('.github/', 'audit/', 'tests/', 'docs/', 'tools/'))]
    hashes = {}
    for path in protected:
        content = (ROOT / path).read_bytes()
        assert_reviewed_source(base, path, content)
        hashes[path] = hashlib.sha256(content).hexdigest()
    if GUIDE_DISPLAY_DATA not in protected and (ROOT / GUIDE_DISPLAY_DATA).is_file():
        assert git('rev-parse', base).decode().strip() == GUIDE_DISPLAY_BASE
        content = (ROOT / GUIDE_DISPLAY_DATA).read_bytes()
        blob = b'blob ' + str(len(content)).encode('ascii') + b'\0' + content
        assert hashlib.sha1(blob).hexdigest() == GUIDE_DISPLAY_DATA_BLOB, GUIDE_DISPLAY_DATA
        hashes[GUIDE_DISPLAY_DATA] = hashlib.sha256(content).hexdigest()
    if any((ROOT/path).exists() for path in LINE_NEW):
        pins = line_pins()
        for path in LINE_NEW:
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == pins[path], path
    # Newly added exhibit assets are not in the baseline tree: pin explicitly.
    pins = json.loads((ROOT/'audit/best-shot-exhibition-20261121/files.json').read_text(encoding='utf-8'))
    assert pins['base_main'] == EXHIBITION_BASE
    assert set(pins['files']) == EXHIBITION_MODIFIED | EXHIBITION_NEW
    for path in EXHIBITION_NEW:
        current = (ROOT / path).read_bytes()
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == pins['files'][path], path
    # Original runtime stays byte-for-byte equal except exact reviewed CPU pins.
    runtime = [p for p in git('ls-tree', '-rz', '--name-only', PR137, 'comments/staging').decode().split('\0') if p]
    runtime += ['comments/package.json', 'comments/package-lock.json']
    runtime += ['comments/staging/registry.mjs']
    for path in runtime:
        assert_staging_source(path, (ROOT/path).read_bytes())
    portal = json.loads(git('show', 'origin/gh-pages:portal-data.json'))
    read = lambda name: json.loads((ROOT/name).read_text(encoding='utf-8'))
    config = json.loads(git('show', 'origin/gh-pages:research-comments-config.json'))
    source_config = read(PUBLIC_CONFIG)
    base_config = json.loads(git('show', f'{base}:{PUBLIC_CONFIG}'))
    assert config in (base_config, source_config)
    registry = read('comments/cases.json')
    sys.path.insert(0, str(ROOT))
    from research_comments import registry_digest, prepare
    from research_ui import build_research_cases
    cases = build_research_cases(portal)
    state = prepare(cases, registry)
    assert not state['pending'], state['pending']
    manifest = read('comments/staging/manifest.json')
    published = json.loads(git('show', 'origin/gh-pages:research-comment-cases.json'))
    assert manifest == published
    assert manifest['registry_sha256'] == registry_digest(registry)
    assert sorted(manifest['active_ids']) == sorted(r['id'] for r in registry['cases'])
    snapshot = json.loads(git('show', 'origin/gh-pages:article-sync-snapshot.json'))
    from bs4 import BeautifulSoup
    selections = set()
    for p in git('ls-tree','-rz','--name-only','origin/gh-pages').decode().split('\0'):
        if p.startswith('best-shots') and p.endswith('.html'):
            selections.update(c['data-selection-id'] for c in BeautifulSoup(git('show',f'origin/gh-pages:{p}'),'html.parser').select('[data-selection-id]'))
    assert selections == {e['selection_id'] for e in read('data/best-shots.json')['entries']}
    for name in ('mushroom-master', 'sources'):
        key = 'mushroom_master' if name == 'mushroom-master' else name
        assert portal['reference_data'][key] == read(f'data/{name}.json')
    artworks = read('audit/ai-image-refresh-20261031/artwork-manifest.json')['assets']
    for row in artworks:
        name = 'assets/'+row['asset']
        assert (ROOT/name).read_bytes() == git('show', f'origin/gh-pages:{name}'), name
    output_names = ['portal-data.json','article-sync-snapshot.json','research-comment-cases.json','research-comments-config.json']
    return {'main':git('rev-parse',base).decode().strip(),
            'published':git('rev-parse','origin/gh-pages').decode().strip(),
            'reviewed_pr137':PR137, 'protected_files':hashes,
            'exact_reviewed_staging_files':runtime, 'registry_sha256':registry_digest(registry),
            'cpu_runtime_review':CPU_BASE,
            'counts':{'photos':len(portal['observations']), 'best_shots':len(selections),
                      'notices':len(read('data/update-notices.json')['events']),
                      'research':len(cases), 'retired':snapshot['payload']['retirement']['retired_count'],
                      'master':len(read('data/mushroom-master.json')['entries']),
                      'sources':len(read('data/sources.json')['sources']), 'webp':len(artworks)},
            'published_hashes':{p:hashlib.sha256(git('show',f'origin/gh-pages:{p}')).hexdigest() for p in output_names},
            'comments_enabled':config['enabled'], 'pending':state['pending'], 'remote_mutations':[]}

if __name__ == '__main__':
    result = collect(sys.argv[2] if len(sys.argv)>2 else 'origin/main')
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='protected_files'},ensure_ascii=False))
