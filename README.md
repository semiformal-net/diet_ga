# Nutrient optimization

Demo code to generate (an unlimited variety of) nutritionally complete diets.

## Filters

I apply default filtering of gross things like baby food, but foods can be filtered to meet any dietary preference.

## Optimization

Default is to minimize *total calories* subject to nutritional completeness. Any other nutritional optimization is possible too: maximize protein, minimize carbs, etc.

### Optimization technique: nested LP/GA. 
 
* Innermost set is a basket of foods. To find the amount of each food that meets nutritional requirements I use an LP solver (`cvxopt`).
* Outer optimization chooses which foods to place in baskets. This uses a genetic algorithm (`deap`). It generates baskets of foods with items that tend to perform well together.
