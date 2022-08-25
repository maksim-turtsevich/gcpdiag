#!/usr/bin/env python3

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
"""gcpdiag main script."""

# pylint: disable=invalid-name

from flask import Flask, request
import os

from gcpdiag import config
from gcpdiag.lint import command as lint_command
import sys

from jira import JIRA

# Initiating a Flask App
app = Flask(__name__)

resource_map = {
    "Apigee": ["apigee"], "Big Data": ["bigquery", "composer", "dataproc"], "App Engine": ["gae"],
    "CI/CD": ["gcb"], "Integration": ["gcb"], "Compute Engine": ["gce"], "Cloud Functions": ["gcf"],
    "Storage": ["gcs"], "Kubernetes Engine": ["gke"], "IAM": ["iam"], "Ass": ["tpu"], "Networking": ["vpc"],
    "All": ["All"]
}


def submit_to_jira(name_of_the_ticket, final_text):

  options = {'server': r"https://devoteamgcloud.atlassian.net/"}
  jira = JIRA(basic_auth=("maksim.turtsevich@devoteam.com", os.getenv("jira_token")), options=options)

  comment = jira.add_comment(name_of_the_ticket, final_text, visibility={'key': 'sd.public.comment'},
                               is_internal=True)


def composing_text(filtered_data):
  final_text = ""

  count = 1
  for rule in filtered_data:
    final_text += str(count) + ")" + " " + rule["rule"] + " (" + rule["status"] + ")" + " - "  + rule["short_message"] + "\n\n"
    final_text += "  " + rule["long_message"] + "\n\n"
    final_text += "  " + "Resources affected: " + "\n" + "\n".join([" - " + res for res in rule["resource"]]) + "\n\n"
    final_text += "  " + "Documentation: " + rule["doc_url"] + "\n\n"
    final_text += "\n\n"
    count += 1
  
  return final_text


def preparing_group_first_element(first_elem):
  first_elem["resource"] = [first_elem["resource"]]
  return first_elem


def grouping(filtered_data):
  grouped_data = []

  first_element = preparing_group_first_element(filtered_data[0])
  grouped_data.append(first_element)

  for i in range(1, len(filtered_data)):
    if filtered_data[i]["rule"] == grouped_data[-1]["rule"]:
      grouped_data[-1]["resource"].append(filtered_data[i]["resource"])
    else:
      group_first_elem = preparing_group_first_element(filtered_data[i])
      grouped_data.append(group_first_elem)
  
  return grouped_data


def filtering(request, final_data):
  filtered_lst_of_rules = []

  lst_of_dicts = request["issue"]["fields"]["customfield_10141"]
  lst_of_needed_resources = {resource_map.get(resource["value"])[0] for resource in lst_of_dicts if resource_map.get(resource["value"])[0]}

  for res in lst_of_needed_resources:

    for rule in final_data:
      if res in rule["rule"]:
        filtered_lst_of_rules.append(rule)

  return filtered_lst_of_rules

def unsupported_fields(request):
  return [res["value"] for res in request["issue"]["fields"]["customfield_10141"]]

@app.route("/", methods=["POST", "GET"])
def request_handler():
  if request.method == "GET":
    return "Endpoint Works!\n"

  # Extracting the data from the request
  request_payload = request.json
  project = request_payload["issue"]["fields"]["customfield_10169"]

  final_data = lint_command.run(project)
  filtered_data = filtering(request_payload, final_data)

  if filtered_data:
    grouped_data = grouping(filtered_data)
    final_text = composing_text(grouped_data)
    submit_to_jira(request_payload["issue"]["key"], final_text)
    
    return final_text
  
  absent_fields = unsupported_fields(request_payload)
  empty_text = f"Unfortunately the following resources: {absent_fields} weren't found on the customer account or\
  they are not supported by gcpdiag :(\n"
  submit_to_jira(request_payload["issue"]["key"], empty_text)

  return empty_text

def main(project):
  # A very simple command-line parser to determine what subcommand is called.
  # Proper argument parsing will be done in the subcommands.
  # print(argv)
  # # make sure we always output UTF-8, even if the terminal falls back to ascii
  # if sys.version_info >= (3, 7):
  #   sys.stdout.reconfigure(encoding='utf-8')

  # if len(argv) == 1 or argv[1] == '--help' or argv[1] == 'help':
  #   print_help()
  # elif argv[1] == 'version' or argv[1] == '--version':
  #   print(f'gcpdiag {config.VERSION}\nCopyright 2021 Google LLC')
  # elif argv[1] == 'lint':
  #   # Replace argv[0:1] with only argv[0] so that argparse works correctly.
  #   sys.argv.pop(0)
  #   sys.argv[0] = 'gcpdiag lint'
  try:
    lint_command.run(project)
  except KeyboardInterrupt:
    print(
        '\n[WARNING] KeyboardInterrupt: Application was interrupted (terminated)',
        file=sys.stderr)
    sys.exit(1)
  # else:
  #   print(f'ERROR: unknown command {argv[1]}. Use --help for help.',
  #         file=sys.stderr)
  #   sys.exit(1)


def print_help():
  print("""gcpdiag 🩺 - Diagnostics for Google Cloud Platform

Usage:
        gcpdiag COMMAND [OPTIONS]

Commands:
        help     Print this help text.
        lint     Run diagnostics on GCP projects.
        version  Print gcpdiag version.

See: gcpdiag COMMAND --help for command-specific usage.""")


if __name__ == '__main__':
  app.run("0.0.0.0", port=8000, debug=True)
  # main("gcp-coe-msp-sandbox")
