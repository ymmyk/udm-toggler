"""A minimal, stateless MCP server (Streamable HTTP transport, JSON responses).

Every POST carries one JSON-RPC message and is answered with one JSON body,
so there is no session to track and nothing to stream. Requests must carry
an OAuth bearer token with the ``mcp`` scope, issued by django-oauth-toolkit.
"""
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.oauth2_backends import get_oauthlib_core

from .handler import UdmHandler
from .models import FirewallRule, Schedule, UserDetail
from .services import set_rule_enabled, set_schedule_enabled, sync_rules


PROTOCOL_VERSIONS = ['2025-11-25', '2025-06-18', '2025-03-26']
SCOPE = 'mcp'

RULE_NOTE = (
    'Rules are block rules: enabled=true means the internet is OFF (blocked) '
    'for that device, enabled=false means it is ON.'
)

TOOLS = [
    {
        'name': 'list_rules',
        'description': f'List firewall rules. {RULE_NOTE} By default only the favorite '
                       'rules shown on the home page are returned.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'include_all': {'type': 'boolean', 'description': 'Include non-favorite rules too.'},
            },
        },
        'annotations': {'readOnlyHint': True},
    },
    {
        'name': 'set_rule',
        'description': f'Enable or disable one firewall rule by id. {RULE_NOTE}',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'rule_id': {'type': 'integer'},
                'enabled': {'type': 'boolean'},
            },
            'required': ['rule_id', 'enabled'],
        },
        'annotations': {'destructiveHint': False, 'idempotentHint': True},
    },
    {
        'name': 'set_all_rules',
        'description': f'Enable or disable every favorite rule at once (Block All / '
                       f'Unblock All). {RULE_NOTE}',
        'inputSchema': {
            'type': 'object',
            'properties': {'enabled': {'type': 'boolean'}},
            'required': ['enabled'],
        },
        'annotations': {'destructiveHint': False, 'idempotentHint': True},
    },
    {
        'name': 'refresh_rules',
        'description': 'Re-sync the rule list and states from the UDM.',
        'inputSchema': {'type': 'object', 'properties': {}},
        'annotations': {'idempotentHint': True},
    },
    {
        'name': 'list_schedules',
        'description': 'List schedules that automatically turn the internet on or off for rules.',
        'inputSchema': {'type': 'object', 'properties': {}},
        'annotations': {'readOnlyHint': True},
    },
    {
        'name': 'set_schedule',
        'description': 'Enable or disable a schedule by id.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'schedule_id': {'type': 'integer'},
                'enabled': {'type': 'boolean'},
            },
            'required': ['schedule_id', 'enabled'],
        },
        'annotations': {'destructiveHint': False, 'idempotentHint': True},
    },
]


class ToolError(Exception):
    pass


def _rule_dict(rule):
    return {'id': rule.id, 'name': rule.name, 'enabled': rule.enabled, 'favorite': rule.favorite}


def _handler():
    detail = UserDetail.shared()
    if detail is None:
        raise ToolError('UDM credentials are not configured')
    return UdmHandler(detail)


def _get_rule(rule_id):
    try:
        return FirewallRule.objects.get(id=rule_id)
    except FirewallRule.DoesNotExist:
        raise ToolError(f'No rule with id {rule_id}')


def list_rules(include_all=False):
    rules = FirewallRule.objects.all() if include_all else FirewallRule.objects.filter(favorite=True)
    return {'rules': [_rule_dict(r) for r in rules.order_by('name')]}


def set_rule(rule_id, enabled):
    rule = _get_rule(rule_id)
    return {'rule': _rule_dict(set_rule_enabled(_handler(), rule, enabled))}


def set_all_rules(enabled):
    handler = _handler()
    rules = FirewallRule.objects.filter(favorite=True).order_by('name')
    return {'rules': [_rule_dict(set_rule_enabled(handler, r, enabled)) for r in rules]}


def refresh_rules():
    sync_rules(_handler())
    return list_rules(include_all=True)


def list_schedules():
    schedules = Schedule.objects.prefetch_related('rules').order_by('name')
    return {'schedules': [{
        'id': s.id,
        'name': s.name,
        'action': s.get_action_display(),
        'days_of_week': s.days_of_week,  # 0 = Monday
        'time': s.time.strftime('%H:%M'),
        'enabled': s.is_enabled,
        'rule_ids': [r.id for r in s.rules.all()],
    } for s in schedules]}


def set_schedule(schedule_id, enabled):
    try:
        schedule = Schedule.objects.get(id=schedule_id)
    except Schedule.DoesNotExist:
        raise ToolError(f'No schedule with id {schedule_id}')
    set_schedule_enabled(schedule, enabled)
    return {'schedule': {'id': schedule.id, 'name': schedule.name, 'enabled': schedule.is_enabled}}


TOOL_FUNCS = {
    'list_rules': list_rules,
    'set_rule': set_rule,
    'set_all_rules': set_all_rules,
    'refresh_rules': refresh_rules,
    'list_schedules': list_schedules,
    'set_schedule': set_schedule,
}


def _call_tool(params):
    name = params.get('name')
    func = TOOL_FUNCS.get(name)
    if func is None:
        raise _RpcError(-32602, f'Unknown tool: {name}')
    try:
        result = func(**(params.get('arguments') or {}))
    except TypeError as e:
        return _tool_result(f'Invalid arguments: {e}', is_error=True)
    except Exception as e:
        return _tool_result(str(e), is_error=True)
    return _tool_result(json.dumps(result), structured=result)


def _tool_result(text, structured=None, is_error=False):
    result = {'content': [{'type': 'text', 'text': text}], 'isError': is_error}
    if structured is not None:
        result['structuredContent'] = structured
    return result


class _RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _dispatch(method, params):
    if method == 'initialize':
        requested = params.get('protocolVersion')
        return {
            'protocolVersion': requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'udm-toggler', 'version': '1.0'},
            'instructions': RULE_NOTE,
        }
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': TOOLS}
    if method == 'tools/call':
        return _call_tool(params)
    raise _RpcError(-32601, f'Method not found: {method}')


def _unauthorized(request):
    metadata_url = request.build_absolute_uri('/.well-known/oauth-protected-resource/mcp')
    response = JsonResponse({'error': 'invalid_token'}, status=401)
    response['WWW-Authenticate'] = (
        f'Bearer resource_metadata="{metadata_url}", scope="{SCOPE}"'
    )
    return response


def _rpc_error(msg_id, code, message):
    return JsonResponse({'jsonrpc': '2.0', 'id': msg_id, 'error': {'code': code, 'message': message}})


@csrf_exempt
def mcp_endpoint(request):
    if request.method != 'POST':
        # No server-initiated stream (GET) or sessions to end (DELETE).
        response = HttpResponse(status=405)
        response['Allow'] = 'POST'
        return response

    valid, _ = get_oauthlib_core().verify_request(request, scopes=[SCOPE])
    if not valid:
        return _unauthorized(request)

    try:
        message = json.loads(request.body)
    except ValueError:
        return _rpc_error(None, -32700, 'Parse error')
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or 'method' not in message:
        return _rpc_error(None, -32600, 'Invalid request')

    if 'id' not in message:
        # Notifications (e.g. notifications/initialized) get no reply.
        return HttpResponse(status=202)

    msg_id = message['id']
    try:
        result = _dispatch(message['method'], message.get('params') or {})
    except _RpcError as e:
        return _rpc_error(msg_id, e.code, e.message)
    return JsonResponse({'jsonrpc': '2.0', 'id': msg_id, 'result': result})
