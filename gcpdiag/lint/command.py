# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""gcpdiag lint command."""

import argparse
import importlib
import logging
import pkgutil
import re
import sys
import os

from gcpdiag import config, hooks, lint, models
from gcpdiag.lint import report_csv, report_json, report_terminal
from gcpdiag.queries import apis

dict_with_vals = {
                  'auth_adc': False, 
                  'auth_key': os.getenv("SECRET"), 
                  'auth_oauth': False, 
                  'project': 'gcp-coe-msp-sandbox', 
                  'billing_project': None, 
                  'show_skipped': False, 
                  'hide_ok': True, 
                  'include': None, 
                  'exclude': None, 
                  'include_extended': False, 
                  'verbose': 0, 
                  'within_days': 3, 
                  'config': None, 
                  'logging_ratelimit_requests': None, 
                  'logging_ratelimit_period_seconds': None, 
                  'logging_page_size': None, 
                  'logging_fetch_max_entries': None, 
                  'logging_fetch_max_time_seconds': None, 
                  'output': 'json'
                  }

def _flatten_multi_arg(arg_list):
  """Flatten a list of comma-separated values, like:
  ['a', 'b, c'] -> ['a','b','c']
  """
  for arg in arg_list:
    yield from re.split(r'\s*,\s*', arg)


def _init_args_parser():
  parser = argparse.ArgumentParser(
      description='Run diagnostics in GCP projects.', prog='gcpdiag lint')

  parser.add_argument(
      '--auth-adc',
      help='Authenticate using Application Default Credentials (default)',
      action='store_true')

  parser.add_argument(
      '--auth-key',
      help='Authenticate using a service account private key file',
      metavar='FILE')

  parser.add_argument(
      '--auth-oauth',
      help='Authenticate using OAuth user authentication (currently '
      'marked as deprecated, consider using other authentication methods)',
      action='store_true')

  parser.add_argument('--project',
                      metavar='P',
                      required=True,
                      help='Project ID of project to inspect')

  parser.add_argument(
      '--billing-project',
      metavar='P',
      help='Project used for billing/quota of API calls done by gcpdiag '
      '(default is the inspected project, requires '
      '\'serviceusage.services.use\' permission)')

  parser.add_argument('--show-skipped',
                      help='Show skipped rules',
                      action='store_true',
                      default=config.get('show_skipped'))

  parser.add_argument('--hide-skipped',
                      help=argparse.SUPPRESS,
                      action='store_false',
                      dest='show_skipped')

  parser.add_argument('--hide-ok',
                      help='Hide rules with result OK',
                      action='store_true',
                      default=config.get('hide_ok'))

  parser.add_argument('--show-ok',
                      help=argparse.SUPPRESS,
                      action='store_false',
                      dest='hide_ok')

  parser.add_argument(
      '--include',
      help=('Include rule pattern (e.g.: `gke`, `gke/*/2021*`). '
            'Multiple pattern can be specified (comma separated, '
            'or with multiple arguments)'),
      action='append')

  parser.add_argument('--exclude',
                      help=('Exclude rule pattern (e.g.: `BP`, `*/*/2022*`)'),
                      action='append')

  parser.add_argument('--include-extended',
                      help=('Include extended rules. Additional rules might '
                            'generate false positives (default: False)'),
                      default=config.get('include_extended'),
                      action='store_true')

  parser.add_argument('-v',
                      '--verbose',
                      action='count',
                      default=config.get('verbose'),
                      help='Increase log verbosity')

  parser.add_argument('--within-days',
                      metavar='D',
                      type=int,
                      help=(f'How far back to search logs and metrics (default:'
                            f" {config.get('within_days')} days)"),
                      default=config.get('within_days'))

  parser.add_argument('--config',
                      metavar='FILE',
                      type=str,
                      help=('Read configuration from FILE'))

  parser.add_argument('--logging-ratelimit-requests',
                      metavar='R',
                      type=int,
                      help=('Configure rate limit for logging queries (default:'
                            f" {config.get('logging_ratelimit_requests')})"))

  parser.add_argument(
      '--logging-ratelimit-period-seconds',
      metavar='S',
      type=int,
      help=('Configure rate limit period for logging queries (default:'
            f" {config.get('logging_ratelimit_period_seconds')} seconds)"))

  parser.add_argument('--logging-page-size',
                      metavar='P',
                      type=int,
                      help=('Configure page size for logging queries (default:'
                            f" {config.get('logging_page_size')})"))

  parser.add_argument(
      '--logging-fetch-max-entries',
      metavar='E',
      type=int,
      help=('Configure max entries to fetch by logging queries (default:'
            f" {config.get('logging_fetch_max_entries')})"))

  parser.add_argument(
      '--logging-fetch-max-time-seconds',
      metavar='S',
      type=int,
      help=('Configure timeout for logging queries (default:'
            f" {config.get('logging_fetch_max_time_seconds')} seconds)"))

  parser.add_argument(
      '--output',
      metavar='FORMATTER',
      default='terminal',
      type=str,
      help=(
          'Format output as one of [terminal, json, csv] (default: terminal)'))

  return parser


def _parse_rule_patterns(patterns):
  if patterns:
    rules = []
    for arg in _flatten_multi_arg(patterns):
      try:
        rules.append(lint.LintRulesPattern(arg))
      except ValueError:
        print(f"ERROR: can't parse rule pattern: {arg}", file=sys.stderr)
        sys.exit(1)
    return rules
  return None


def _load_repository_rules(repo: lint.LintRuleRepository):
  """Find and load all lint rule modules dynamically"""
  for module in pkgutil.walk_packages(
      lint.__path__,  # type: ignore
      lint.__name__ + '.'):
    if module.ispkg:
      try:
        m = importlib.import_module(f'{module.name}')
        repo.load_rules(m)
      except ImportError as err:
        print(f"ERROR: can't import module: {err}", file=sys.stderr)
        continue


def _initialize_output_formater() -> lint.LintReport:
  report: lint.LintReport
  if config.get('output') == 'json':
    report = report_json.LintReportJson(
        log_info_for_progress_only=(config.get('verbose') == 0),
        show_ok=not config.get('hide_ok'),
        show_skipped=config.get('show_skipped'))
  elif config.get('output') == 'csv':
    report = report_csv.LintReportCsv(
        log_info_for_progress_only=(config.get('verbose') == 0),
        show_ok=not config.get('hide_ok'),
        show_skipped=config.get('show_skipped'))
  else:
    report = report_terminal.LintReportTerminal(
        log_info_for_progress_only=(config.get('verbose') == 0),
        show_ok=not config.get('hide_ok'),
        show_skipped=config.get('show_skipped'))
  return report


def run(project) -> int:
  # del argv

  # Initialize argument parser
  # parser = _init_args_parser()
  # args = parser.parse_args()
  # print(f"args: {args}")
  # print(f"var_args: {vars(args)}")
  dict_with_vals["project"] = project

  # Allow to change defaults using a hook function.
  # hooks.set_lint_args_hook(args)

  # Initialize Context.
  context = models.Context(project_id=dict_with_vals["project"])

  # Initialize configuration
  config.init(dict_with_vals, context.project_id, report_terminal.is_cloud_shell())

  # Rules name patterns that shall be included or excluded
  include_patterns = _parse_rule_patterns(config.get('include'))
  exclude_patterns = _parse_rule_patterns(config.get('exclude'))

  # Initialize Repository, and Tests.
  repo = lint.LintRuleRepository(config.get('include_extended'))
  _load_repository_rules(repo) # Load rules (with name, id, rule, class, exec_func, prep_func, etc.)

  # ^^^ If you add rules directory, update also
  # pyinstaller/hook-gcpdiag.lint.py and bin/precommit-required-files

  # Initialize proper output formater
  report = _initialize_output_formater() # Initialization of output formatter

  # Logging setup.
  logging_handler = report.get_logging_handler() # getting logging.Handler class
  logger = logging.getLogger()
  # Make sure we are only using our own handler
  logger.handlers = []
  logger.addHandler(logging_handler)
  if config.get('verbose') >= 2:
    logger.setLevel(logging.DEBUG)
  else:
    logger.setLevel(logging.INFO)
  # Disable logging from python-api-client, unless verbose is turned on
  if config.get('verbose') == 0:
    gac_http_logger = logging.getLogger('googleapiclient.http')
    gac_http_logger.setLevel(logging.ERROR)

  # Deprecation warning
  if config.get('auth_oauth'):
    logger.warning(
        'DeprecationWarning: The oauth authentication is '
        'deprecated and will be removed in the future versions. Consider '
        'using other authentication methods.')

  # Start the reporting
  report.banner()
  report.lint_start(context)

  # Verify that we have access and that the CRM API is enabled
  apis.verify_access(context.project_id)

  # Run the tests.
  exit_code, data = repo.run_rules(context, report, include_patterns,
                             exclude_patterns) # context (Class with project name)
                                               # report output_formatter (json class)
                                               # repo (storage of rules)
  # hooks.post_lint_hook(report)

  # Exit 0 if there are no failed rules.
  return data
