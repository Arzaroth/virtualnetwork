#!/usr/bin/python3.3 -O

from pyrser import grammar,meta
from pyrser.directives import ignore
from network import Host, Router
import sys

def insensitiveCase(s):
    return "[" + " ".join("['" + "'|'".join(x) + "']" for x in map((lambda each: [each.lower(), each.upper()]), s)) + "]"

class MapParser(grammar.Grammar):
    entry = "Map"
    grammar = """

    Map = [#init_map(_) @ignore("null") [[[Hosts:h #add_host(_, h)] | [Routers:r #add_router(_, r)]] eol*]+
    #link_hosts(_) eof]

    Hosts = [#init_host(_) '[' ws {host} ws ']' eol+ [[Name | Ip | TTL | Route]:r #add_fhost(_, r)]+]

    Routers = [#init_router(_) '[' ws {router} ws ']' eol+ [[Name | Ip | TTL | Route]:r #add_frouter(_, r)]+]

    Name = [ws {name} ws '=' ws id:i #ret_f(_, "id", i) ws eol+]

    Ip = [ws {ip} ws '=' ws cidraddr:c #ret_f(_, "ip", c) ws eol+]

    TTL = [ws {ttl} ws '=' ws num:n #ret_f(_, "ttl", n) ws eol+]

    Route = [ws {route} ws '=' ws [[{default}:c ws id:i #ret_f(_, "route", c, i)]
    | [cidraddr:c ws id:i #ret_f(_, "route", c, i)]] ws eol+]

    cidraddr = [num '.' num '.' num '.' num '/' num]

    ws = [[' ' | '\r' | '\t']*]
    """.format(host = insensitiveCase("Host"),
               router = insensitiveCase("Router"),
               route = insensitiveCase("Route"),
               ip = insensitiveCase("IP"),
               ttl = insensitiveCase("TTL"),
               name = insensitiveCase("Name"),
               default = insensitiveCase("Default"),
               internet = insensitiveCase("Internet"))


@meta.hook(MapParser)
def init_map(self, ast):
    ast.network = {}
    ast.routes = {}
    return True

@meta.hook(MapParser)
def init_host(self, ast):
    self.init_map(ast)
    ast.network["route"] = []
    return True

@meta.hook(MapParser)
def init_router(self, ast):
    self.init_host(ast)
    ast.network["ips"] = []
    return True

@meta.hook(MapParser)
def link_hosts(self, ast):
    for k,v in ast.routes.items():
        for x in v:
            if x[1] not in ast.network:
                raise Exception("Unknown host ({0}) for {1} route.".format(x[1], k))
            ast.network[k].addRoute(ast.network[x[1]], x[0])
    return True

def base_add(ast, h):
    if "name" not in h.network:
        raise Exception("Missing name field for given host:\n{0}".format(self.value(h)))
    if h.network["name"] in ast.network:
        raise Exception("Redefinion of {0}.".format(h.network["name"]))
    ast.routes[h.network["name"]] = h.network["route"][::]

@meta.hook(MapParser)
def add_host(self, ast, h):
    base_add(ast, h)
    if "ip" not in h.network:
        raise Exception("Missing ip field for given host:\n{0}".format(self.value(h)))
    if "ttl" in h.network:
        ast.network[h.network["name"]] = Host(h.network["name"],
                                              h.network["ip"], h.network["ttl"])
    else:
        ast.network[h.network["name"]] = Host(h.network["name"],
                                              h.network["ip"])
    return True

@meta.hook(MapParser)
def add_router(self, ast, h):
    base_add(ast, h)
    if not h.network["ips"]:
        raise Exception("Missing ip field for given host")
    if "ttl" in h.network:
        ast.network[h.network["name"]] = Router(h.network["name"],
                                                *h.network["ips"], ttl = h.network["ttl"])
    else:
        ast.network[h.network["name"]] = Router(h.network["name"],
                                                *h.network["ips"])
    return True

@meta.hook(MapParser)
def ret_f(self, ast, *args):
    ast.retvals = [args[0]]
    ast.retvals.extend([self.value(x) for x in args[1:]])
    return True

@meta.hook(MapParser)
def add_fhost(self, ast, r):
    def reg_name(ast, name):
        ast.network["name"] = name[0]
    def reg_ip(ast, ip):
        ast.network["ip"] = ip[0]
    def reg_ttl(ast, ttl):
        ast.network["ttl"] = ttl[0]
    def reg_route(ast, route):
        ast.network["route"].append(route)
    fmap = {'id' : reg_name,
            'ip' : reg_ip,
            'ttl' : reg_ttl,
            'route' : reg_route}
    if r.retvals[0] in fmap:
        fmap[r.retvals[0]](ast, r.retvals[1:])
    return True

@meta.hook(MapParser)
def add_frouter(self, ast, r):
    def reg_name(ast, name):
        ast.network["name"] = name[0]
    def reg_ip(ast, ip):
        ast.network["ips"].append(ip[0])
    def reg_ttl(ast, ttl):
        ast.network["ttl"] = ttl[0]
    def reg_route(ast, route):
        ast.network["route"].append(route)
    fmap = {'id' : reg_name,
            'ip' : reg_ip,
            'ttl' : reg_ttl,
            'route' : reg_route}
    if r.retvals[0] in fmap:
        fmap[r.retvals[0]](ast, r.retvals[1:])
    return True
