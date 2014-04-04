from PIL import Image
import os
import random
from itertools import product, starmap, islice
import uuid
import itertools
from dijkstar import Graph, find_path, NoPathError
# Configurable settings
min_pass_count = 25  # Minimum and maximum number of passes to make.
max_pass_count = 35  # The more passes, the smoother it will be.
wall_chance = .525  # The chance of a wall appearing in the initial generation.
constant_symmetry = False  # Makes it symmetric on each pass.
output_folder = "generated/"  # The folder to output images into.
num_images = 10  # The number of images to generate.
width = 40
height = 40


class GenerationError(Exception):
    pass


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class Block:
    __metaclass__ = Singleton

    def __init__(self):
        self.image = Image.open(self.image_loc)

    def get_neighbor_coords(self):
        return [(self.x + i, self.y + j) for i, j in
                product([-1, 0, 1], [-1, 0, 1]) if
                (0 <= self.x + i <= width) and (0 <= self.y + i <= height)]


class Flag(Block):
    pass


class Floor(Block):
    image_loc = "floor.png"


class RedFlag(Flag):
    image_loc = "red_flag.png"


class BlueFlag(Flag):
    image_loc = "blue_flag.png"


class Wall(Block):
    image_loc = "wall.png"

class Level:
    def __init__(self, width=40, height=40):
        self.width = width
        self.height = height
        self.base_blocks = (Floor, Wall)
        self.grid = [[self.get_cell() for _ in range(width)]
                     for _ in range(height)]

    def get_neighbors(self, x, y):
        xi = (0, -1, 1) if 0 < x < len(self.grid) - 1 else (
            (0, -1) if x > 0 else (0, 1))
        yi = (0, -1, 1) if 0 < y < len(self.grid[0]) - 1 else (
            (0, -1) if y > 0 else (0, 1))
        return islice(
            starmap((lambda a, b: self.grid[x + a][y + b]), product(xi, yi)), 1,
            None)

    def get_neighbor_coords(self, x, y):
        xi = (0, -1, 1) if 0 < x < len(self.grid) - 1 else (
            (0, -1) if x > 0 else (0, 1))
        yi = (0, -1, 1) if 0 < y < len(self.grid[0]) - 1 else (
            (0, -1) if y > 0 else (0, 1))
        return [(x+a, y+b) for a, b in product(xi, yi)]

    def get_neighbors(self, x, y):
        return [self.grid[a][b] for a,b in self.get_neighbor_coords(x, y)]

    def run_pass(self):
        for x, y in product(range(self.width), range(self.height)):
            node = self.grid[x][y]
            neighbors = self.get_neighbors(x, y)
            #print(len(neighbors))
            wall_count = 0

            for neighbor in neighbors:
                if isinstance(neighbor, Wall):
                    wall_count += 1
            if wall_count >= 5 and random.random() > 0.025:
                self.grid[x][y] = Wall()
            else:
                self.grid[x][y] = Floor()
        self.grid[0] = [Wall() for _ in range(self.width)]
        self.grid[-1] = [Wall() for _ in range(self.width)]
        for x in range(self.height):
            self.grid[x][0] = Wall()
            self.grid[x][-1] = Wall()

    def make_symmetric(self):
        s = self.height // 2
        y = self.grid[0:s]
        z = [a for a in reversed(y)]
        for a in range(len(z)):
            z[a] = list(reversed(z[a]))
        y.extend(z)
        self.grid = y

    def make_image(self):
        image = Image.new("RGBA", (self.width * 40, self.height * 40))
        filename = "{}.png".format(uuid.uuid4())
        path = os.path.join(output_folder, filename)
        for x in range(self.width):
            for y in range(self.height):
                cell = self.grid[x][y]
                image.paste(cell.image, (y * 40, x * 40))
        try:
            image.save(path)
        except KeyboardInterrupt:
            if os.path.isfile(path):
                os.remove(path)  # Perform cleanup to avoid a broken PNG.
            raise

    def find_longest_path(self):
        x, y = (0, 0)
        for x in range(self.width):
            for y in range(self.height):
                if isinstance(self.grid[x][y], Floor):
                    pairs = (-1, -1, 0, 0, 1, 1)
                    sums = itertools.permutations(pairs, 2)
                    neighbors = [isinstance(z, Floor) for z in
                                 itertools.chain.from_iterable(
                                     [self.get_neighbors(x + a, y + b) for a, b
                                      in sums])]
                    if all(neighbors):
                        break
            else:
                continue
            break

        self.grid[-2 - x][-2 - y] = BlueFlag()
        self.grid[x + 1][y + 1] = RedFlag()


    def floodFill(self, x, y, o):
        to_fill = set()
        to_fill.add((x, y))
        while len(to_fill) > 0 and (x < self.width and y < self.height):
            x, y = to_fill.pop()
            if not isinstance(self.grid[x][y], Floor):
                continue
            a = (x - 1, y)
            b = (x + 1, y)
            c = (x, y - 1)
            d = (x, y + 1)
            if a not in o:
                to_fill.add(a)
            if b not in o:
                to_fill.add(b)
            if c not in o:
                to_fill.add(c)
            if d not in o:
                to_fill.add(d)
            o = o.union(to_fill.copy())
        if float(len(o))/float(self.width*self.height) < .4:
            raise GenerationError("Not enough open space.")
        return o

    def smooth(self):

        while True:
            a = set()
            b = set()
            x1 = random.randrange(0, self.width)
            x2 = random.randrange(0, self.width)
            y1 = random.randrange(0, self.height)
            y2 = random.randrange(0, self.height)
            n1 = self.floodFill(x1, y1, a)
            n2 = self.floodFill(x2, y2, b)
            if n1 == n2:
                break
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) not in n1:
                    self.grid[x][y] = Wall()

    def get_cell(self):
        x = random.random()
        if x <= wall_chance:
            return Wall()
        else:
            return Floor()

    def make_graph(self):
        graph = Graph()
        for x, y in product(range(self.width), range(self.height)):
            if isinstance(self.grid[x][y],
                          Floor) or isinstance(self.grid[x][y], Flag):
                for i,j in self.get_neighbor_coords(x, y):
                    if isinstance(self.grid[i][j],
                          Floor) or isinstance(self.grid[i][j], Flag):
                        graph.add_edge((x,y), (i,j), 1)
        return graph

    def ensure_traversable(self):
        graph = self.make_graph()
        blue = None
        red = None
        for x, y in product(range(self.width), range(self.height)):
            cell = self.grid[x][y]
            if isinstance(cell, BlueFlag):
                blue = (x,y)
            elif isinstance(cell, RedFlag):
                red = (x,y)
            if blue is not None and red is not None:
                break
        path = find_path(graph, blue, red)
        print path
        return path

def generate_level(x=40, y=40):
    z = Level(x, y)
    #print z.get_neighbor_coords(21,11)
    #return
    for x in range(random.randrange(min_pass_count, max_pass_count)):
        if constant_symmetry:
            z.make_symmetric()

        z.run_pass()

    #print "Smoothing..."
    z.smooth()

    #print "Transforming map to be symmetric..."
    z.make_symmetric()


    #print "Placing flags..."
    z.find_longest_path()

    z.ensure_traversable()
    #print "Making image."
    z.make_image()

    #print "Done!\n\n"


if __name__ == "__main__":
    print "Starting batch generation of {} images".format(num_images)
    n = 1
    while n <= num_images:
        try:
            print "Creating map..."
            generate_level()
            n += 1
            print "Level generated!\n\n"
        except (IndexError), e:
            print "Generation failure. Restarting."
        except NoPathError, e:
            #print e
            print "No path between flags, restarting."
        except GenerationError, e:
            print "Not enough open space. Restarting."