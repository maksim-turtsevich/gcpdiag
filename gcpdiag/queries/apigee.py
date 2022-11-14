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
"""Queries related to Apigee."""

from typing import Dict, Iterable, List, Mapping, Optional

import googleapiclient.errors

from gcpdiag import caching, config, models
from gcpdiag.queries import apis, apis_utils
from gcpdiag.utils import GcpApiError


class ApigeeEnvironment(models.Resource):
  """Represents an Apigee Environment
    https://cloud.google.com/apigee/docs/reference/apis/apigee/rest/v1/organizations.environments#Environment
    """

  def __init__(self, apigee_org, env_name: str):
    super().__init__(project_id=apigee_org.project_id)
    self.org_name = apigee_org.name
    self.name = env_name

  @property
  def full_path(self) -> str:
    return f'organizations/{self.org_name}/environments/{self.name}'


class ApigeeOrganization(models.Resource):
  """Represents an Apigee Organization
    https://cloud.google.com/apigee/docs/reference/apis/apigee/rest/v1/organizations#Organization
    """
  _resource_data: Optional[dict]
  _environments: List[ApigeeEnvironment]

  # It is possible to create an Apigee organization resource in another GCP project,
  # set the resource_data as optional to avoid permission issues while accessing another GCP project
  def __init__(self,
               project_id: str,
               org_name: str,
               resource_data: Optional[dict] = None):
    super().__init__(project_id=project_id)
    self._resource_data = resource_data
    self.name = org_name

  @property
  def full_path(self) -> str:
    return f'organizations/{self.name}'

  @property
  def environments(self) -> Iterable[ApigeeEnvironment]:
    if self._resource_data is None:
      return []

    return [
        ApigeeEnvironment(self, env)
        for env in self._resource_data.get('environments', [])
    ]

  @property
  def runtime_type(self) -> str:
    if self._resource_data is None:
      return ''
    return self._resource_data['runtimeType']

  @property
  def runtime_database_encryption_key_name(self) -> str:
    if self._resource_data is None:
      return ''

    return self._resource_data.get('runtimeDatabaseEncryptionKeyName', '')


class EnvironmentGroup(models.Resource):
  """Represents an Apigee Environment Group
    https://cloud.google.com/apigee/docs/reference/apis/apigee/rest/v1/organizations.envgroups#resource:-environmentgroup
    """
  _resource_data: dict

  def __init__(self, apigee_org: ApigeeOrganization, resource_data):
    super().__init__(project_id=apigee_org.project_id)
    self._resource_data = resource_data
    self.org_name = apigee_org.name

  @property
  def name(self) -> str:
    return self._resource_data['name']

  @property
  def full_path(self) -> str:
    return f'organizations/{self.org_name}/envgroups/{self.name}'

  @property
  def host_names(self) -> List[str]:
    return self._resource_data['hostnames']


class ApigeeInstance(models.Resource):
  """Represents an Apigee Runtime Instance
    https://cloud.google.com/apigee/docs/reference/apis/apigee/rest/v1/organizations.instances#Instance
    """
  _resource_data: dict

  def __init__(self, apigee_org: ApigeeOrganization, resource_data):
    super().__init__(project_id=apigee_org.project_id)
    self._resource_data = resource_data
    self.org_name = apigee_org.name

  @property
  def name(self) -> str:
    return self._resource_data['name']

  @property
  def full_path(self) -> str:
    return f'organizations/{self.org_name}/instances/{self.name}'

  @property
  def disk_encryption_key_name(self) -> str:
    return self._resource_data.get('diskEncryptionKeyName', '')


@caching.cached_api_call
def get_org(context: models.Context) -> Optional[ApigeeOrganization]:
  """Get Apigee organizations matching the GCP Project Id"""
  if not apis.is_enabled(context.project_id, 'apigee'):
    return None
  apigee_api = apis.get_api('apigee', 'v1', context.project_id)
  # Apigee Organization : GCP Project = 1 : 1
  org_list_query = apigee_api.organizations().list(parent='organizations')
  try:
    resp = org_list_query.execute(num_retries=config.API_RETRIES)
    if 'organizations' not in resp:
      return None
    for resp_o in resp['organizations']:
      if 'organization' not in resp_o or 'projectId' not in resp_o:
        raise RuntimeError('missing data in organizations.list response')
      if context.project_id == resp_o['projectId']:
        org_name = resp_o['organization']
        get_org_query = apigee_api.organizations().get(
            name=f'organizations/{org_name}')
        get_org_resp = get_org_query.execute(num_retries=config.API_RETRIES)
        return ApigeeOrganization(context.project_id, resp_o['organization'],
                                  get_org_resp)
  except googleapiclient.errors.HttpError as err:
    raise GcpApiError(err) from err
  return None


@caching.cached_api_call
def get_envgroups(
    apigee_org: ApigeeOrganization) -> Mapping[str, EnvironmentGroup]:
  """Get Environment group list by organization name, caching the result."""
  envgroups: Dict[str, EnvironmentGroup] = {}
  apigee_api = apis.get_api('apigee', 'v1')

  request = apigee_api.organizations().envgroups().list(
      parent=f'organizations/{apigee_org.name}')
  for envgroup in apis_utils.list_all(
      request,
      next_function=apigee_api.organizations().envgroups().list_next,
      response_keyword='environmentGroups'):
    envgroups[envgroup['name']] = EnvironmentGroup(apigee_org=apigee_org,
                                                   resource_data=envgroup)
  return envgroups


@caching.cached_api_call
def get_envgroups_attachments(envgroup_name: str) -> List[str]:
  """Get Environment group attachments by environment group name, caching the result."""
  environments: List[str] = []
  apigee_api = apis.get_api('apigee', 'v1')

  request = apigee_api.organizations().envgroups().attachments().list(
      parent=envgroup_name)
  for attachments in apis_utils.list_all(
      request,
      next_function=apigee_api.organizations().envgroups().attachments(
      ).list_next,
      response_keyword='environmentGroupAttachments'):
    environments.append(attachments['environment'])
  return environments


@caching.cached_api_call
def get_instances(
    apigee_org: ApigeeOrganization) -> Mapping[str, ApigeeInstance]:
  """Get instance list from Apigee Organization, caching the result."""
  instances: Dict[str, ApigeeInstance] = {}
  # Not supported for Apigee hybrid.
  if apigee_org.runtime_type == 'HYBRID':
    return instances

  apigee_api = apis.get_api('apigee', 'v1')
  request = apigee_api.organizations().instances().list(
      parent=f'organizations/{apigee_org.name}')
  for instance in apis_utils.list_all(
      request,
      next_function=apigee_api.organizations().instances().list_next,
      response_keyword='instances'):
    instances[instance['name']] = ApigeeInstance(apigee_org=apigee_org,
                                                 resource_data=instance)
  return instances


@caching.cached_api_call
def get_instances_attachments(instance_name: str) -> List[str]:
  """Get instance attachments by instance name, caching the result."""
  environments: List[str] = []
  if not instance_name:
    return environments

  apigee_api = apis.get_api('apigee', 'v1')
  request = apigee_api.organizations().instances().attachments().list(
      parent=instance_name)
  for attachments in apis_utils.list_all(request,
                                         next_function=apigee_api.organizations(
                                         ).instances().attachments().list_next,
                                         response_keyword='attachments'):
    environments.append(attachments['environment'])
  return environments
