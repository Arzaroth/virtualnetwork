#!/usr/bin/python3.3 -O
import re

prog = re.compile("^(\d{1,3})[.](\d{1,3})[.](\d{1,3})[.](\d{1,3})/(\d{1,2})$")

def iptobinpad(ip):
    return ''.join([bin(int(i))[2:].zfill(8) for i in ip])

def CIDRtoIP(mask):
    """
    return the subnet IP extracted from CIDR notation
    """
    ip = ("1" * mask).ljust(32, '0')
    return ".".join([str(int(ip[i:i+8], 2)) for i in range(0, 32, 8)])

class Host(object):
    """
    The Host class is used to represent a host on a subnet
    Each machine on a subnet must have differents hostname and ip
    You can set TTL to a value between 0 and 255. Default value will be 64
    """
    def __init__(self, name, ip, ttl = 64):
        """
        The IP field must look like that "192.168.0.1/24" according to CIDR notation
        If either of TTL or IP values are bad, it will throw a ValueError exception
        """
        self._name = name
        self._ttl = int(ttl)
        if not 0 <= self._ttl <= 255:
            raise ValueError("Bad TTL value")
        self._ip, self._mask = self._checkIp(ip)
        self._cidr = ip
        self._routes = {}
        self._defaultroute = None

    def _checkIp(self, ip):
        se = prog.match(ip)
        if not se or True in [int(i) > 255 for i in se.groups()[:4]] or int(se.group(5)) > 32:
            raise ValueError("""
            Not a valid ip for {name} (was {ip})
            Note that this tool only handle CIDR notation
            """.format(name = self._name, ip = ip))
        return se.groups()[:4], int(se.group(5))

    def showRoutes(self):
        """
        return a string representing all the routes for a Host instance
        """
        s = "{0}:\n{pad}{1} -- {2}\n".format(self._name, ".".join(self._ip), CIDRtoIP(self._mask), pad = 1 * " ")
        s += "  routes:\n"
        for k,v in self._routes.items():
            s += "{pad}{rule} -> {route}\n".format(rule = k, route = v._name, pad = 1 * "  ")
        if self._defaultroute is not None:
            s += "{pad}Default -> {route}\n".format(route = self._defaultroute._name, pad = 2 * "  ")
        return s

    def _canConnect__(self, ip, mask, ignore = False):
        return iptobinpad(ip)[:max(mask, self._mask if not ignore else mask)] == iptobinpad(self._ip)[:max(mask, self._mask if not ignore else mask)]

    def _canConnect(self, otherhost):
        """
        return a boolean
        True if the two hosts can communicate directly, False otherwise
        If the otherhost argument isn't an instance of the Host class, it will throw a TypeError
        """
        if not isinstance(otherhost, Host):
            raise TypeError("First argument must be of Host type")
        if isinstance(otherhost, Router):
            return otherhost._canConnect(self)
        return self._canConnect__(otherhost._ip, otherhost._mask)

    def addRoute(self, route, ip = None):
        """
        Add a route for future connections to remote hosts
        If no IP is provided or is "Default", set the Default route
        If the IP isn't a valid CIDR notation, return False
        return True otherwise
        throw a TypeError if the route argument isn't an instance of the Router class
        """
        if not isinstance(route, Router):
            raise TypeError("First argument must be of Router type")
        if ip is None or ip.lower() == "default":
            self._defaultroute = route
        else:
            try:
                self._checkIp(ip)
            except ValueError:
                return False
            else:
                self._routes[ip] = route
        return True

    def canConnect(self, remotehost, ttl = None, basehost = None):
        """
        return a boolean
        True if the two hosts can communicate directly or using their routes, False otherwise
        If the remotehost argument isn't an instance of the Host class, it will throw a TypeError
        """
        if not isinstance(remotehost, Host):
            raise TypeError("First argument must be of Host type")
        ttl = self._ttl if ttl is None else ttl - 1
        basehost = self if basehost is None else basehost
        if ttl == 0:
            return (False, 0)
        if self._canConnect(remotehost):
            print("{0} -> {1}".format(self._name, remotehost._name))
            return remotehost.canConnect(basehost, None, basehost) if remotehost is not basehost else (True, ttl)
        restrict = []
        for k,v in self._routes.items():
            i,m = k.split('/')
            if remotehost._canConnect__(i.split('.'), int(m), True):
                restrict.append([int(m),v])
        if restrict:
            p = tuple(zip(*restrict))[0]
            print("{0} -> {1}".format(self._name, restrict[max(range(len(p)), key=p.__getitem__)][1]._name))
            return restrict[max(range(len(p)), key=p.__getitem__)][1].canConnect(remotehost, ttl, basehost) if self._canConnect(restrict[max(range(len(p)), key=p.__getitem__)][1]) else (False, 0)
        if self._defaultroute is not None and self._canConnect(self._defaultroute):
            print("{0} -> {1}".format(self._name, self._defaultroute._name))
            return self._defaultroute.canConnect(remotehost, ttl, basehost)
        return (False, 0)

class Router(Host):
    """
    A router is like a super Host which can have multiple ip addresses on differents subnets
    Default TTL for a router is set to 255
    """
    def __init__(self, name, ip, *args, **kwargs):
        super().__init__(name, ip, kwargs.get("ttl", 255))
        self._cidrs = [self._cidr]
        self._ips = [(self._ip, self._mask)]
        del self._ip, self._mask, self._cidr
        for i in args:
            self._ips.append(self._checkIp(i))

    def _canConnect__(self, ip, mask, ignore = False):
        return any([iptobinpad(ip)[:max(mask, m if not ignore else mask)] == iptobinpad(i)[:max(mask, m if not ignore else mask)] for i,m in self._ips])

    def _canConnect(self, otherhost):
        """
        return a boolean
        True if the two hosts can communicate directly, False otherwise
        If the otherhost argument isn't an instance of the Host class, it will throw a TypeError
        """
        if not isinstance(otherhost, Host):
            raise TypeError("First argument must be of Host type")
        if isinstance(otherhost, Router):
            return any([self._canConnect__(i, m) for i,m in otherhost._ips])
        return self._canConnect__(otherhost._ip, otherhost._mask)

    def showRoutes(self):
        """
        return a string representing all the routes for a Router instance
        """
        s = "{0}:\n".format(self._name)
        for x in self._ips:
            s += "{pad}{1} -- {2}\n".format(self._name, ".".join(x[0]), CIDRtoIP(x[1]), pad = 1 * "  ")
        s += "  routes:\n"
        for k,v in self._routes.items():
            s += "{pad}{rule} -> {route}\n".format(rule = k, route = v._name, pad = 2 * "  ")
        if self._defaultroute is not None:
            s += "{pad}Default -> {route}\n".format(route = self._defaultroute._name, pad = 2 * "  ")
        return s
