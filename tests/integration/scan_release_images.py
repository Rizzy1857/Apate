"""Scan exact ARM64 image IDs with a fresh DB and an offline pinned scanner.

Only the initial scanner/DB download uses networking. Image scans mount exported
images and this new evidence directory; they do not mount the Docker socket or
the repository. Reports include unfixed findings and all severities.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


SCANNER = 'aquasec/trivy@sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('core', 'redis', 'postgres'):
        parser.add_argument('--' + role, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    cache = output/'scanner-cache'
    cache.mkdir(mode=0o700)
    outcome = {'result': 'FAIL', 'started_at': datetime.now(timezone.utc).isoformat(),
               'scanner_reference': SCANNER, 'images': {}}

    def run(cmd, timeout=300):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr[-8000:] or result.stdout[-8000:])
        return result.stdout.strip()

    def scanner(network, *cmd):
        return run(['docker', 'run', '--rm', '--network', network,
            '-e', 'TRIVY_DISABLE_VEX_NOTICE=true', '-e', 'TRIVY_SKIP_VERSION_CHECK=true',
            '-v', str(cache)+':/cache', '-v', str(output)+':/results', SCANNER, *cmd])

    try:
        # Resolve tags to immutable IDs before any export or scan.
        for role in ('core', 'redis', 'postgres'):
            data = json.loads(run(['docker', 'image', 'inspect', getattr(args, role)]))[0]
            assert data['Architecture'] == 'arm64' and data['Os'] == 'linux'
            outcome['images'][role] = {'reference': getattr(args, role),
                'id': data['Id'], 'architecture': data['Architecture'],
                'repo_digests': data.get('RepoDigests', []),
                'layers': data['RootFS']['Layers']}
        # Download with cache only; no image exports, source or Docker socket.
        print('Downloading the pinned scanner and fresh vulnerability database', flush=True)
        download = run(['docker', 'run', '--rm', '--network', 'bridge',
            '-e', 'TRIVY_SKIP_VERSION_CHECK=true', '-v', str(cache)+':/cache',
            SCANNER, 'image', '--cache-dir', '/cache', '--download-db-only'])
        (output/'db-download.log').write_text(download+'\n')
        version = scanner('none', '--cache-dir', '/cache', 'version', '--format', 'json')
        (output/'scanner.json').write_text(version+'\n')
        outcome['scanner'] = json.loads(version)
        for role, identity in outcome['images'].items():
            print('Exporting and scanning '+role+' '+identity['id'], flush=True)
            archive = output/(role+'.tar')
            run(['docker', 'image', 'save', '--output', str(archive), identity['id']])
            with archive.open('rb') as f:
                identity['archive_sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
            scanner('none', 'image', '--cache-dir', '/cache', '--skip-db-update',
                '--skip-java-db-update', '--offline-scan', '--scanners', 'vuln',
                '--format', 'json', '--input', '/results/'+role+'.tar',
                '--output', '/results/trivy-'+role+'.json')
            report_path = output/('trivy-'+role+'.json')
            report = json.loads(report_path.read_text())
            with report_path.open('rb') as f:
                identity['report_sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
            assert report['Metadata']['DiffIDs'] == identity['layers'], 'Scan layer mismatch'
            findings = [v for result in report.get('Results', [])
                        for v in result.get('Vulnerabilities', [])]
            identity['severity_counts'] = dict(Counter(v['Severity'] for v in findings))
            identity['unique_advisories'] = sorted({v['VulnerabilityID'] for v in findings})
            identity['high_critical'] = sorted({v['VulnerabilityID'] for v in findings
                                              if v['Severity'] in ('HIGH', 'CRITICAL')})
            identity['fixable_high_critical'] = sorted({v['VulnerabilityID'] for v in findings
                if v['Severity'] in ('HIGH', 'CRITICAL') and v.get('FixedVersion')})
            print(json.dumps({'image': role, 'counts': identity['severity_counts'],
                              'fixable_high_critical': identity['fixable_high_critical']}), flush=True)
        outcome['result'] = 'SCANNED'  # A completed scan is not risk acceptance.
    except BaseException as error:
        outcome['error'] = repr(error)
        raise
    finally:
        outcome['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output/'scan-summary.json').write_text(json.dumps(outcome, indent=2)+'\n')


if __name__ == '__main__':
    main()
