"""
Overview:

  provide a server that monitors log files.

provide the following actions:

  1. add a monitor

     When a monitor is defined via the HTTP interface, its configuration
     is written/overwritten to disk.

     The attributes of a monitor are:

       a. a filename
       b. a file() object
       c. a set of rules
         Rules contain:
           i.  a regex
           ii. an action
             Actions can be:
               1. increment, takes a list of counters to increment
               2. store, takes a list of stores to append to
           iii. a stop/continue flag
               A flag which determines whether to continue
               to the next rule or stop evaluating rules.

  2. Add/Delete a rule

  3. Change the filename of an existing monitor
     (closes the existing file object and reopens with new filename)

  4. List all counters
  5. List all sets of saved log entries
  6. List the log entries of a specified set of log entries
  7. Show a specified set of counters.

"""



import re
import collections


from twisted.internet import task
from twisted.web import resource, server



class MonitorsView(resource.Resource):
    """
    Displays a list of monitor names and associated filename
    """


    def __init__(self):
        resource.Resource.__init__(self)
        self.monitors = {}


    def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "\n".join("%s:%s" % (m.name, m.filename)
                                for i, m in self.monitors.iteritems()) + "\n"


    def add(self, monitor):
        self.monitors[monitor.name] = monitor


    def getChild(self, name, request):
        return MonitorView(self.monitors[name])



class MonitorView(resource.Resource):

    """
    Serves as the parent node for the StoresView and CountersView
    views.  Just displays a static string if called directly.
    """


    def __init__(self, monitor):
        resource.Resource.__init__(self)
        self.monitor = monitor
        self.putChild('stores', StoresView(self.monitor))
        self.putChild('counters', CountersView(self.monitor))


    def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "stores\ncounters\n"



class StoresView(resource.Resource):

    """
    Returns a list of stores
    """


    def __init__(self, monitor):
        resource.Resource.__init__(self)
        self.monitor = monitor


    def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "\n".join(k for k in self.monitor.stores.iterkeys()) + "\n"


    def getChild(self, name, request):
        return StoreView(self.monitor.stores[name])



class CountersView(resource.Resource):

    """
    Returns a list of counters
    """


    def __init__(self, monitor):
        resource.Resource.__init__(self)
        self.monitor = monitor


    def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "\n".join(k for k in self.monitor.counters.iterkeys()) + "\n"


    def getChild(self, name, request):
        return CounterView(self.monitor.counters[name])



class CounterView(resource.Resource):

    """
    Returns the count for the specified counter.
    """


     def __init__(self, counter):
        resource.Resource.__init__(self)
        self.counter = counter


     def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "%s\n" % self.counter



class StoreView(resource.Resource):


    """
    Returns the lines in the specified store.
    """


     def __init__(self, store):
        resource.Resource.__init__(self)
        self.store = store


     def render(self, request):
        request.setHeader('Content-Type', 'text/plain')
        return "\n".join(self.store) + "\n"



class Rule(object):

    """
    A regex.  Allows for incrementing counters and/or appending
    messages to "stores" of log messages.  A rule can also force
    rule processing in a FileMonitor to stop.
    """


    def __init__(self, regex):
        self.regex = regex
        self.re = re.compile(regex)
        self.counters = []
        self.stores = []
        self.stop = False


    def check(self, line, counters, stores):
        match = self.re.search(line)

        if match:
            groups = match.groups()
            if len(groups):
                line = " ".join(groups)

            print line

            for counter in self.counters:
                counters[counter] += 1

            for store in self.stores:
                stores[store].append(line)

        return self.stop



class FileMonitor(object):

    """
    Monitors a log file and holds counters, stores
    of interesting messages, and a list of Rules.
    """


    file = None


    def __init__(self, name, filename, block_size=8192):
        self.name = name
        self.filename = filename
        self.data = ''
        self.block_size = block_size
        self.stores = collections.defaultdict(list)
        self.counters = collections.defaultdict(int)
        self.rules = []


    @property
    def filename(self):
        return self._filename


    @filename.setter
    def filename(self, filename):
        if self.file:
            self.file.close()
            self.file = None
        self._filename = filename


    def loop(self, frequency=5):
        self.lc = task.LoopingCall(self.read)
        self.lc.start(frequency, True)


    def lineRead(self, line):
        for rule in self.rules:
            # check returns True if rules processing should stop
            # or False if rules processing should continue
            if rule.check(line, self.counters, self.stores):
                break


    def read(self):
        if not self.file:
            try:
                self.file = open(self.filename)
            except IOError:
                print "%s: unable to open yet" % self.filename
                return

        self.data += self.file.read(self.block_size)

        contents = self.data.rsplit('\n', 1)
        if len(contents) == 2:
            self.data = contents[1]
            for line in contents[0].splitlines():
                self.lineRead(line)



def main():
    from twisted.internet import reactor

    eRule = Rule('ERROR:*(.*)$')
    eRule.stores.append('errors')
    eRule.counters.append('errors')

    wRule = Rule('WARNING:*(.*)$')
    wRule.stores.append('warnings')
    wRule.counters.append('warnings')

    ft = FileMonitor('junk', "/tmp/junk.txt")
    ft.rules = [eRule, wRule]
    ft.loop()

    root = resource.Resource()
    monitorsView = MonitorsView()
    monitorsView.add(ft)

    root.putChild('monitors', monitorsView)

    site = server.Site(root)
    reactor.listenTCP(8088, site)

    reactor.run()



if __name__ == "__main__":
    main()


