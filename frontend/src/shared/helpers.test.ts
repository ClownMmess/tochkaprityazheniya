import {describe,it,expect} from 'vitest';
import {filterQuery,initialFilters} from './filters';
import {safeUrl} from './api';
import {choiceLink} from './max';
describe('frontend contract',()=>{
 it('preserves zero budget and category list',()=>{const q=new URLSearchParams(filterQuery({...initialFilters,price_max:'0',categories:['stand-up','concert']}));expect(q.get('price_max')).toBe('0');expect(q.getAll('categories')).toEqual(['stand-up','concert']);});
 it('constructs exact choice deep link',()=>{expect(choiceLink('our_bot','Ab_12')).toBe('https://max.ru/our_bot?startapp=choice_Ab_12');});
 it('rejects unsafe links',()=>{expect(safeUrl('javascript:alert(1)')).toBeUndefined();expect(safeUrl('https://example.com')).toBe('https://example.com/');});
 it('rejects malformed choice token',()=>{expect(()=>choiceLink('bot','../../secret')).toThrow();});
});
